from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import get_settings


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def select_diverse_items(
    items: list[dict[str, Any]],
    limit: int,
    *,
    excluded_article_ids: set[str] | None = None,
    excluded_group_ids: set[str] | None = None,
    repeat_after: Any = None,
) -> list[dict[str, Any]]:
    excluded_articles = excluded_article_ids or set()
    excluded_groups = excluded_group_ids or set()
    normalized_repeat_after = _as_utc(repeat_after)

    def updated_event_coverage(item: dict[str, Any]) -> bool:
        updated_at = _as_utc(item.get("event_updated_at"))
        published_at = _as_utc(item.get("published_at"))
        return bool(
            normalized_repeat_after
            and updated_at
            and published_at
            and updated_at > normalized_repeat_after
            and published_at > normalized_repeat_after
        )

    remaining = [
        item for item in items
        if (
            str(item["article"].get("_id")) not in excluded_articles
            or (
                item.get("event_group_id")
                and str(item["event_group_id"]) in excluded_groups
                and updated_event_coverage(item)
            )
        )
        and not (
            item.get("event_group_id")
            and str(item["event_group_id"]) in excluded_groups
            and not updated_event_coverage(item)
        )
    ]
    selected: list[dict[str, Any]] = []
    group_ids: set[str] = set()
    category_counts: dict[str, int] = {}
    while remaining and len(selected) < limit:
        eligible = [
            (index, item) for index, item in enumerate(remaining)
            if not item.get("event_group_id") or str(item["event_group_id"]) not in group_ids
        ]
        if not eligible:
            break
        best_score = max(item["relevance_score"] for _, item in eligible)
        tolerance = get_settings().recommendation_diversity_tolerance
        competitive = [
            (index, item) for index, item in eligible
            if item["relevance_score"] >= best_score - tolerance
        ]
        best_index, _ = min(
            competitive,
            key=lambda pair: (
                category_counts.get(str(pair[1]["article"].get("category") or "World News"), 0),
                -pair[1]["relevance_score"],
            ),
        )
        item = remaining.pop(best_index)
        selected.append(item)
        if item.get("event_group_id"):
            group_ids.add(str(item["event_group_id"]))
        category = str(item["article"].get("category") or "World News")
        category_counts[category] = category_counts.get(category, 0) + 1
        if item.get("event_group_id"):
            remaining = [
                candidate for candidate in remaining
                if str(candidate.get("event_group_id")) != str(item["event_group_id"])
            ]
    return selected
