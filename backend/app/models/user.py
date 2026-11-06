from __future__ import annotations

from datetime import datetime, timezone


class User:
    def __init__(
        self,
        full_name: str,
        email: str,
        password_hash: str,
        interests: list[str] | None = None,
        is_active: bool = True,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.full_name = full_name
        self.email = email.lower().strip()
        self.password_hash = password_hash
        self.interests = interests or []
        self.is_active = is_active
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or self.created_at

    def to_document(self) -> dict:
        return {
            "full_name": self.full_name,
            "email": self.email,
            "password_hash": self.password_hash,
            "interests": self.interests,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
