from pathlib import Path

import yaml

from worthit.benefits.schema import BenefitConfig, MatchRule

REQUIRED_FIELDS = ["id", "label", "amount", "period", "detection_mode", "match"]
VALID_PERIODS = {"monthly", "semiannual_calendar"}
VALID_MODES = {"spend_threshold", "credit_match"}


class BenefitConfigError(ValueError):
    pass


def load_benefits(path: str | Path) -> list[BenefitConfig]:
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    entries = data.get("benefits", [])
    if not entries:
        raise BenefitConfigError(f"No benefits defined in {path}")

    result = []
    seen_ids = set()
    for entry in entries:
        for field_name in REQUIRED_FIELDS:
            if field_name not in entry:
                raise BenefitConfigError(
                    f"Benefit {entry.get('id', '<unknown>')!r} is missing required field {field_name!r}"
                )

        benefit_id = entry["id"]
        if benefit_id in seen_ids:
            raise BenefitConfigError(f"Duplicate benefit id: {benefit_id!r}")
        seen_ids.add(benefit_id)

        if entry["period"] not in VALID_PERIODS:
            raise BenefitConfigError(
                f"Benefit {benefit_id!r} has invalid period {entry['period']!r}, "
                f"expected one of {VALID_PERIODS}"
            )
        if entry["detection_mode"] not in VALID_MODES:
            raise BenefitConfigError(
                f"Benefit {benefit_id!r} has invalid detection_mode {entry['detection_mode']!r}, "
                f"expected one of {VALID_MODES}"
            )

        purchase_hint = entry.get("purchase_hint")
        result.append(
            BenefitConfig(
                id=benefit_id,
                label=entry["label"],
                amount=float(entry["amount"]),
                period=entry["period"],
                detection_mode=entry["detection_mode"],
                match=MatchRule.from_dict(entry["match"]),
                amount_cap=float(entry["amount_cap"]) if entry.get("amount_cap") is not None else None,
                enrollment_required=bool(entry.get("enrollment_required", False)),
                posting_lag_days=int(entry.get("posting_lag_days", 0)),
                purchase_hint=MatchRule.from_dict(purchase_hint) if purchase_hint else None,
                notes=entry.get("notes", ""),
            )
        )
    return result
