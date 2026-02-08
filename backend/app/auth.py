from fastapi import Header, HTTPException


from .config import PCP_API_KEY


def verify_api_key(authorization: str = Header(default="")):
    """Validate Bearer token for dashboard API calls."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:]
    if token != PCP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return token
