from __future__ import annotations

import re
from collections import Counter

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "modern",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "you", "your", "yours", "yourself", "yourselves", "also", "new", "said",
}

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'/-]*")


def extract_keywords(title: str | None, description: str | None, max_keywords: int = 8) -> list[str]:
    combined = " ".join(part for part in [title or "", description or ""] if part)
    if not combined:
        return []

    tokens = []
    for match in _WORD_RE.finditer(combined):
        token = match.group(0).lower()
        if len(token) <= 2:
            continue
        if token in STOP_WORDS:
            continue
        tokens.append(token)

    if not tokens:
        return []

    counts = Counter(tokens)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    keywords = [word for word, _ in ranked[:max_keywords]]
    return keywords
