"""All services related to chatbot"""

import os

from langchain.storage import InMemoryStore
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils.data_loader import PDFLoader, IncidentDocLoader
from api.utils.logger import logger
from .agents import (
    TEXT_COLLECTION_NAME,
    build_rag_graph,
)
from .schemas import ChatRecord
from .models import (
    Chat as ChatModel,
    IngestedFile as IngestedFileModel,
    RoleTypes,
)
from api.utils.hash_file import get_file_hash
from api.utils.vs_weaviate_utils import get_client

RETRIEVE_CHATS_NUM = 50
IMPORT_FILES_FOLDER = "./data"


def find_all_data_files(folder_url: str):
    technical_files = []
    incident_summary_files = []
    for file in os.listdir(folder_url):
        if file.endswith(".pdf"):
            technical_files.append(f"{folder_url}/{file}")
    for file in os.listdir(f"{folder_url}/incident_summaries"):
        if file.endswith(".pdf"):
            incident_summary_files.append(
                f"{folder_url}/incident_summaries/{file}"
            )
    return technical_files, incident_summary_files


async def load_technical_pdf_files(file_urls: list[str], db: AsyncSession):
    """Load technical PDF files, like runbook, engineering docs"""
    with get_client() as client:
        pdf_loader = PDFLoader(client, TEXT_COLLECTION_NAME)
        error_messages = []
        for file_url in file_urls:
            pdf_file_name = file_url.split("/")[-1]
            pdf_file_hash = get_file_hash(file_url)
            result = await IngestedFileModel.find_by_file_hash(
                db=db, file_hash=pdf_file_hash
            )
            if not result:
                if await pdf_loader.load(file_url):
                    await IngestedFileModel.create(
                        db=db, file_name=pdf_file_name, file_hash=pdf_file_hash
                    )
                else:
                    error_messages.append(
                        f"Failed to load PDF file {pdf_file_name}"
                    )
            else:
                logger.info(f"Already ingested {file_url}, skip it")

        return error_messages


async def load_incident_docs(files: list[str], db: AsyncSession) -> list[str]:
    """Load incident summary document files for later multi-vector retriever, file format is PDF with texts and charts"""
    error_messages = []
    if not files:
        return error_messages

    store = InMemoryStore()
    with get_client() as client:
        incident_doc_loader = IncidentDocLoader(
            object_store=store,
            client=client,
            summary_collection_name=TEXT_COLLECTION_NAME,
        )
        for file_url in files:
            file_name = file_url.split("/")[-1]
            file_hash = get_file_hash(file_url)
            result = await IngestedFileModel.find_by_file_hash(
                db=db, file_hash=file_hash
            )
            if not result:
                if incident_doc_loader.load(file_url):
                    await IngestedFileModel.create(
                        db=db, file_name=file_name, file_hash=file_hash
                    )
                else:
                    error_messages.append(
                        f"Failed to load incident analysis file {file_name}"
                    )
            else:
                logger.info(f"Already ingested {file_name}, skip it")
        return error_messages


async def gen_knowledgebase(db: AsyncSession):
    """Ingest all raw data files, indexing and save them into DB or vector DB"""
    error_messages = []
    technical_files, incident_summary_files = find_all_data_files(
        IMPORT_FILES_FOLDER
    )

    try:
        loading_technical_files_errors = await load_technical_pdf_files(
            file_urls=technical_files, db=db
        )
        if loading_technical_files_errors:
            error_messages.extend(loading_technical_files_errors)
        loading_incident_summaries_errors = await load_incident_docs(
            files=incident_summary_files, db=db
        )
        if loading_incident_summaries_errors:
            error_messages.extend(loading_incident_summaries_errors)
    except Exception as e:
        logger.error(f"Something wrong when ingesting files: {str(e)}")
        return {"status": "Failed", "error": str(e)}

    if error_messages:
        return {"status": "Failed", "error": "\n".join(error_messages)}
    return {"status": "Success", "error": None}


async def gen_ai_completion(
    db: AsyncSession, user_id: int, question: str
) -> str:
    """Use RAG with agents to generate AI completion for given question"""
    graph = build_rag_graph()

    chat_history = await ChatModel.find_recent_chat_history(
        db=db, user_id=user_id, limit=2 * RETRIEVE_CHATS_NUM
    )
    # If question was asked recently, just return recent answer from DB, this should improve user experience
    if question in chat_history.keys() and chat_history[question]:
        return chat_history[question]

    await ChatModel.create(
        db=db, user_id=user_id, role_type=RoleTypes.HUMAN, content=question
    )
    response = graph.invoke({"question": question, "chat_history": []})
    completion = response["inter_steps"][-1].log
    await ChatModel.create(
        db=db, user_id=user_id, role_type=RoleTypes.AI, content=completion
    )

    return completion


async def get_chat_history(db: AsyncSession, user_id: int) -> list[ChatRecord]:
    """Load chat history for given user"""
    chat_history = await ChatModel.find_by_userid(db, user_id)
    return chat_history
