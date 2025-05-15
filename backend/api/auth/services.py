import os
import jwt
from datetime import datetime, timedelta, UTC

from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from api.user.schemas import User
from api.user import services as user_services

ACCESS_TOKEN_SECRET = os.environ.get("ACCESS_TOKEN_SECRET", "")
ACCESS_TOKEN_ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

pw_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pw_context.verify(plain_password, hashed_password)


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    user = await user_services.get_by_name(db, username)
    error_msg = "Incorrect username or password"
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
    if not verify_password(password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)

    return user


def decode_jwt(token: str) -> dict:
    return jwt.decode(
        token, ACCESS_TOKEN_SECRET, algorithms=[ACCESS_TOKEN_ALGORITHM]
    )


def create_access_token(data: dict, expires_in: timedelta | None) -> str:
    to_encode = data.copy()
    if expires_in:
        expire = datetime.now(UTC) + expires_in
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})

    access_token = jwt.encode(
        to_encode, ACCESS_TOKEN_SECRET, algorithm=ACCESS_TOKEN_ALGORITHM
    )

    return access_token
