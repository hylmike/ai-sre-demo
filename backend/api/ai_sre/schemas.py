"""Chatbot schemas and customized types used by chatbot services"""

from datetime import datetime

from pydantic import BaseModel


class ChatRecord(BaseModel):
    id: int
    role_type: str
    content: str
    created: datetime


class ChatCompletionRequest(BaseModel):
    query: str
