import json
from dataclasses import dataclass

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_update import LinkTokenCreateRequestUpdate
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from worthit.config import PLAID_CLIENT_ID, PLAID_ENV, PLAID_SECRET

CLIENT_NAME = "Amex Benefit Tracker"
# Single local user - this is a single-player hobby tool, not a multi-tenant app.
CLIENT_USER_ID = "worthit-local-user"


class ItemLoginRequiredError(Exception):
    """Raised when Plaid reports the linked Item needs Link 'update mode'
    re-authentication (ITEM_LOGIN_REQUIRED) - a recurring, expected event for
    Amex connections, not an exceptional failure."""


class PlaidSyncError(Exception):
    """A recoverable Plaid or network failure during transaction sync."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _plaid_error_code(exc: ApiException) -> str | None:
    if not exc.body:
        return None
    try:
        return json.loads(exc.body).get("error_code")
    except (ValueError, AttributeError):
        return None


def get_client() -> plaid_api.PlaidApi:
    host = plaid.Environment.Production if PLAID_ENV == "production" else plaid.Environment.Sandbox
    configuration = plaid.Configuration(
        host=host,
        api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(access_token: str | None = None) -> str:
    """access_token=None -> initial link flow. access_token set -> update mode,
    used to fix an ITEM_LOGIN_REQUIRED reconnect without creating a duplicate Item."""
    client = get_client()
    kwargs = dict(
        client_name=CLIENT_NAME,
        language="en",
        country_codes=[CountryCode("US")],
        user=LinkTokenCreateRequestUser(client_user_id=CLIENT_USER_ID),
    )
    if access_token:
        kwargs["access_token"] = access_token
        kwargs["update"] = LinkTokenCreateRequestUpdate()
    else:
        kwargs["products"] = [Products("transactions")]

    request = LinkTokenCreateRequest(**kwargs)
    response = client.link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str) -> tuple[str, str]:
    client = get_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    return response.access_token, response.item_id


@dataclass
class SyncResult:
    added: list[dict]
    modified: list[dict]
    removed: list[str]
    next_cursor: str


def sync_transactions(access_token: str, cursor: str | None) -> SyncResult:
    client = get_client()
    original_cursor = cursor

    # Plaid can mutate transaction data while a multi-page sync is in flight.
    # Their required recovery is to discard every page and restart from the
    # cursor used for page one. Bound the retries so an unhealthy Item cannot
    # keep a web request open forever.
    for attempt in range(3):
        added, modified, removed = [], [], []
        next_cursor = original_cursor
        has_more = True

        while has_more:
            request_kwargs = {"access_token": access_token, "count": 500}
            # The Plaid SDK rejects cursor=None. Initial sync must omit it.
            if next_cursor is not None:
                request_kwargs["cursor"] = next_cursor
            request = TransactionsSyncRequest(**request_kwargs)
            try:
                response = client.transactions_sync(request)
            except ApiException as exc:
                code = _plaid_error_code(exc) or "PLAID_API_ERROR"
                if code == "ITEM_LOGIN_REQUIRED":
                    raise ItemLoginRequiredError() from exc
                if code == "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION":
                    break
                raise PlaidSyncError(code) from exc
            except Exception as exc:
                raise PlaidSyncError("PLAID_NETWORK_ERROR") from exc

            added.extend(t.to_dict() for t in response.added)
            modified.extend(t.to_dict() for t in response.modified)
            removed.extend(t.transaction_id for t in response.removed)
            next_cursor = response.next_cursor
            has_more = response.has_more
        else:
            return SyncResult(
                added=added,
                modified=modified,
                removed=removed,
                next_cursor=next_cursor,
            )

    raise PlaidSyncError("TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION")
