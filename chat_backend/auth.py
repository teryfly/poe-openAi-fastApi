from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials.credentials.startswith("sk-test") and not credentials.credentials.startswith("poe-sk"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    return credentials.credentials
