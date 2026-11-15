"""The trust engine: rate every source (0 to 100) and every fact (0 to 1) with no manual checking.

It measures how believable the evidence is, not whether it is true (docs/system_overview.md section 4).
Settings and starting weights are in config/trust.yaml. A component that cannot be measured yet is None
and is left out; the remaining weights are rescaled, so scores stay comparable.
"""

from __future__ import annotations

from datetime import date, datetime

from .core import config

COMPONENTS = ["authority", "provenance", "freshness", "completeness", "quality", "agreement", "track_record"]


def _cfg() -> dict:
    return config("trust")


def tier(score: float) -> str:
    t = _cfg()["tiers"]
    return "A" if score >= t["A"] else "B" if score >= t["B"] else "C" if score >= t["C"] else "D"


def combine(components: dict[str, float | None]) -> tuple[float, list[str]]:
    """Weighted mean of the measured components on a 0-100 scale. Returns (score, components used)."""
    w = _cfg()["weights"]
    used = [c for c in COMPONENTS if components.get(c) is not None]
    total = sum(w[c] for c in used)
    if not used or total == 0:
        return 0.0, []
    return round(100 * sum(w[c] * components[c] for c in used) / total, 1), used


def authority(connector_type: str | None = None, source: str | None = None, kind: str | None = None) -> float:
    c = _cfg()
    if source and source in c["authority_by_source"]:
        return c["authority_by_source"][source]
    if kind:
        return c["authority_by_kind"].get(kind, c["authority_by_kind"]["unknown"])
    return c["authority_by_type"].get(connector_type or "", c["authority_by_kind"]["unknown"])


def provenance(licence: str | None, url: str | None, retrieved: str | None) -> float:
    return round(0.5 * bool(licence) + 0.3 * bool(url) + 0.2 * bool(retrieved), 3)


def refresh_days(connector_type: str | None) -> int:
    c = _cfg()
    return c["expected_refresh_days"].get(connector_type or "", c["default_refresh_days"])


def freshness(age_days: float | None, expected_days: float) -> float | None:
    """1 while within the expected refresh interval, falling linearly to 0 at four times that."""
    if age_days is None:
        return None
    if age_days <= expected_days:
        return 1.0
    return round(max(0.0, 1 - (age_days - expected_days) / (3 * expected_days)), 3)


def age_days(retrieved: str | None, today: date | None = None) -> int | None:
    if not retrieved:
        return None
    d = datetime.fromisoformat(str(retrieved)[:10]).date()
    return max(0, ((today or date.today()) - d).days)


def source_score(components: dict[str, float | None]) -> dict:
    score, used = combine(components)
    return {
        "score": score,
        "tier": tier(score),
        "components": {
            c: (None if components.get(c) is None else round(components[c], 3)) for c in COMPONENTS
        },
        "used": used,
    }


def cap_tier(result: dict, highest: str = "B", reason: str = "") -> dict:
    """Never let a source rise above `highest` (an unclear licence caps it at B: usable, not shareable)."""
    order = "ABCD"
    if order.index(result["tier"]) < order.index(highest):
        result = result | {"tier": highest, "capped": reason}
    return result


def fact_confidence(
    source_score_100: float,
    extraction: float = 1.0,
    age: float | None = None,
    half_life_days: float | None = None,
    corroborations: int = 0,
    conflicts: int = 0,
) -> float:
    """source score x extraction x freshness decay x corroboration - conflict penalty, kept in 0..1."""
    f = _cfg()["fact"]
    decay = 0.5 ** (age / half_life_days) if age is not None and half_life_days else 1.0
    boost = 1 + f["corroboration_bonus"] * min(corroborations, f["max_corroborations"])
    pen = f["conflict_penalty"] * min(conflicts, f["max_conflicts"])
    return round(min(1.0, max(0.0, (source_score_100 / 100) * extraction * decay * boost - pen)), 3)


def shown_as(confidence: float | None) -> str:
    """What the assistant may say: confirmed, reported (name the source) or unknown (never stated as fact)."""
    if confidence is None:
        return "unknown"
    s = _cfg()["fact"]["shown_as"]
    return (
        "confirmed"
        if confidence >= s["confirmed"]
        else "reported"
        if confidence >= s["reported"]
        else "unknown"
    )
