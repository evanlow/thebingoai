from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class LogoutRequest(BaseModel):
    refresh_token: str


class DeleteAccountRequest(BaseModel):
    refresh_token: str | None = None
