from pydantic import BaseModel, HttpUrl

class AnonymousAuthRequest(BaseModel):
    display_name: str
    avatar_url: HttpUrl | None = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
