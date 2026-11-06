from __future__ import annotations

from typing import Any

SUMMARY_FIELDS = {
    "short_summary",
    "medium_summary",
    "detailed_summary",
    "key_points",
    "important_facts",
}
FACT_FIELDS = {"people", "organizations", "locations", "dates", "numbers"}


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Summary list field must be an array")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("Summary list entries must be strings")
        text = item.strip()
        if text:
            if len(text) > 1000:
                raise ValueError("Summary list entries are too long")
            cleaned.append(text)
    if len(cleaned) > 10:
        raise ValueError("Summary list contains too many entries")
    return cleaned


def validate_summary_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Summary payload must be a dictionary")
    if set(payload) != SUMMARY_FIELDS:
        raise ValueError("Summary payload contains missing or unexpected fields")

    summary_fields = ["short_summary", "medium_summary", "detailed_summary"]
    normalized: dict[str, Any] = {}
    for field in summary_fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is missing or invalid")
        if len(value.strip()) > 5000:
            raise ValueError(f"{field} is too long")
        normalized[field] = value.strip()

    key_points = _normalize_string_list(payload.get("key_points"))
    if len(key_points) > 5:
        raise ValueError("Summary contains too many key points")
    normalized["key_points"] = key_points

    important_facts = payload.get("important_facts")
    if not isinstance(important_facts, dict):
        raise ValueError("important_facts must be an object")
    if set(important_facts) != FACT_FIELDS:
        raise ValueError("important_facts contains missing or unexpected fields")
    normalized_facts = {
        name: _normalize_string_list(important_facts[name])
        for name in sorted(FACT_FIELDS)
    }

    normalized["important_facts"] = normalized_facts
    return normalized
