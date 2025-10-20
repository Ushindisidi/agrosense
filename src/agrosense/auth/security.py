from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Dict
import secrets
import os

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
API_KEY_NAME = "X-API-Key"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# In-memory user store (replace with database in production)
users_db = {
    "farmer1": {
        "username": "farmer1",
        "email": "farmer1@agrosense.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "role": "farmer",
        "region": "Nairobi",
        "disabled": False
    },
    "admin": {
        "username": "admin",
        "email": "admin@agrosense.com",
        "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU0TZ/.v8Eq6",
        "role": "admin",
        "region": "Nairobi",
        "disabled": False
    }
}

api_keys_db = {
    "agrosense_demo_key_12345": {
        "name": "Demo Key",
        "role": "farmer",
        "region": "Nairobi",
        "active": True
    }
}

# Password utilities
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Token utilities
def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[Dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None

# Authentication dependencies
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    api_key: Optional[str] = Security(api_key_header)
) -> Optional[Dict]:
    """Optional auth - returns None if not authenticated"""
    # Try JWT
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload and payload.get("sub") in users_db:
            user = users_db[payload["sub"]]
            if not user["disabled"]:
                return {
                    "username": user["username"],
                    "email": user["email"],
                    "role": user["role"],
                    "region": user["region"],
                    "auth_method": "jwt"
                }
    
    # Try API Key
    if api_key in api_keys_db:
        key_data = api_keys_db[api_key]
        if key_data["active"]:
            return {
                "username": key_data["name"],
                "role": key_data["role"],
                "region": key_data["region"],
                "auth_method": "api_key"
            }
    
    return None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    api_key: Optional[str] = Security(api_key_header)
) -> Dict:
    """Required authentication"""
    user = await get_current_user_optional(credentials, api_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication"
        )
    return user

def require_role(allowed_roles: list):
    """Role-based access control"""
    async def role_checker(user: Dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user
    return role_checker