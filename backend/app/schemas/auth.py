from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    confirm_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Full name is required")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Confirm password must be at least 8 characters long")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Confirm password must be no more than 72 UTF-8 bytes")
        return value

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context) -> None:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def validate_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value
