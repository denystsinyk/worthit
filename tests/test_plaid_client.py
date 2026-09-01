import json
from unittest.mock import MagicMock, patch

from plaid.exceptions import ApiException

from worthit import plaid_client


def _response(next_cursor="cursor-1", has_more=False):
    response = MagicMock()
    response.added = []
    response.modified = []
    response.removed = []
    response.next_cursor = next_cursor
    response.has_more = has_more
    return response


def test_initial_sync_omits_none_cursor():
    client = MagicMock()
    client.transactions_sync.return_value = _response()

    with patch("worthit.plaid_client.get_client", return_value=client):
        result = plaid_client.sync_transactions("access-token", None)

    request = client.transactions_sync.call_args.args[0]
    assert "cursor" not in request
    assert result.next_cursor == "cursor-1"


def test_incremental_sync_includes_existing_cursor():
    client = MagicMock()
    client.transactions_sync.return_value = _response(next_cursor="cursor-2")

    with patch("worthit.plaid_client.get_client", return_value=client):
        result = plaid_client.sync_transactions("access-token", "cursor-1")

    request = client.transactions_sync.call_args.args[0]
    assert request.cursor == "cursor-1"
    assert result.next_cursor == "cursor-2"


def test_sync_restarts_from_original_cursor_after_pagination_mutation():
    first_page = _response(next_cursor="page-2", has_more=True)
    mutation = ApiException(status=400, reason="mutation")
    mutation.body = json.dumps(
        {"error_code": "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"}
    )
    completed = _response(next_cursor="cursor-complete")
    client = MagicMock()
    client.transactions_sync.side_effect = [first_page, mutation, completed]

    with patch("worthit.plaid_client.get_client", return_value=client):
        result = plaid_client.sync_transactions("access-token", None)

    requests = [call.args[0] for call in client.transactions_sync.call_args_list]
    assert "cursor" not in requests[0]
    assert requests[1].cursor == "page-2"
    assert "cursor" not in requests[2]
    assert result.next_cursor == "cursor-complete"
