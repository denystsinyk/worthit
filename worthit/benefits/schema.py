from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MatchRule:
    # Substrings are checked case-insensitively against merchant_name and name.
    # Multiple substrings within one rule use AND semantics (all must match).
    merchant_contains: list[str] = field(default_factory=list)
    description_contains: list[str] = field(default_factory=list)
    # Alternative rules (OR semantics) - a transaction matches if ANY of these sub-rules match.
    merchant_credit_pairs: list["MatchRule"] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict | None) -> "MatchRule":
        data = data or {}
        pairs = [MatchRule.from_dict(p) for p in data.get("merchant_credit_pairs", [])]
        return MatchRule(
            merchant_contains=list(data.get("merchant_contains", [])),
            description_contains=list(data.get("description_contains", [])),
            merchant_credit_pairs=pairs,
        )


@dataclass
class BenefitConfig:
    id: str
    label: str
    amount: float
    period: Literal["monthly", "semiannual_calendar"]
    detection_mode: Literal["spend_threshold", "credit_match"]
    match: MatchRule
    amount_cap: float | None = None
    enrollment_required: bool = False
    posting_lag_days: int = 0
    purchase_hint: MatchRule | None = None
    notes: str = ""
