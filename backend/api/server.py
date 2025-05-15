from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.database.db import session_manager, create_all_tables
from api.auth.auth_router import auth_router
from api.user.user_router import user_router
from api.user.services import create_user, get_all_users
from api.user.schemas import UserForm
from api.user.models import Roles
from api.ai_sre.ai_sre_router import ai_sre_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Function handles app startup and shutdown events"""
    await create_all_tables()
    # Create default admin user for demo purpose
    async with session_manager.session() as session:
        all_users = await get_all_users(session)
        if len(all_users) == 0:
            await create_user(
                session,
                UserForm(username="admin", password="54321", role=Roles.ADMIN),
            )
    yield
    if session_manager.engine is not None:
        await session_manager.close()


server = FastAPI(lifespan=lifespan, debug=True)

origins = ["http://localhost:4000"]

server.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@server.get("/status")
async def check_api():
    return {"status": "Connected to API successfully"}


# Routers
server.include_router(
    user_router,
    prefix="/api/users",
    tags=["users"],
    responses={404: {"description": "Not Found"}},
)

server.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["auth"],
    responses={401: {"description": "You are not authorized"}},
)

server.include_router(
    ai_sre_router,
    prefix="/api/ai-sre",
    tags=["chatbot"],
    responses={404: {"description": "Not Found"}},
)
