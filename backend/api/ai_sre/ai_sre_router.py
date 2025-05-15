"""API endpoints related to chatbot services"""

from fastapi import APIRouter, Depends

from .services import (
    gen_ai_completion,
    get_chat_history,
    gen_knowledgebase,
)
from .schemas import ChatCompletionRequest
from api.dependencies.db import DBSessionDep
from api.dependencies.auth import CurrentUserDep, valid_is_authenticated

ai_sre_router = APIRouter()


@ai_sre_router.post(
    "/gen-knowledgebase", dependencies=[Depends(valid_is_authenticated)]
)
async def gen_knowledgebase_api(db: DBSessionDep):
    """Generate RAG knowledge base from input webs and docs, and save into vector database"""
    result = await gen_knowledgebase(db)
    return result


@ai_sre_router.post(
    "/chat-completion", dependencies=[Depends(valid_is_authenticated)]
)
async def chat_completion(
    chat_input: ChatCompletionRequest, db: DBSessionDep, user: CurrentUserDep
):
    """Generate AI completion for user question. combine info from chat history and knowledge base"""
    completion = await gen_ai_completion(db, user.id, chat_input.query)

    return {"chat_completion": completion}


@ai_sre_router.get(
    "/chat-history", dependencies=[Depends(valid_is_authenticated)]
)
async def chat_history(db: DBSessionDep, user: CurrentUserDep):
    """Load chat history belong to current user"""
    chats = await get_chat_history(db, user.id)
    return {"chat_history": chats}
