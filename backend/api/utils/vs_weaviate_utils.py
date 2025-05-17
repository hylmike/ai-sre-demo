"""All util classes and functions related to Weaviate vector store"""

import os

import weaviate
from weaviate import WeaviateClient
from weaviate.collections import Collection
from langchain_weaviate import WeaviateVectorStore
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain.storage import LocalFileStore

from api.utils.llm_gpt_utils import embedding_function

TEXT_COLLECTION_NAME = "demo_text_collection"
SUMMARY_COLLECTION_NAME = "demo_summary_collection"

OBJECT_STORE_URL = './data/object-store'
EXCESSIVE_ERROR_THRESHOLD = 10


def get_client() -> WeaviateClient:
    # Weaviate deployed locally in docker, with url: http://localhost:8080
    # If different, here should use different config or function
    host = os.environ.get("WEAVIATE_HOST", "127.0.0.1")
    port = int(os.environ.get("WEAVIATE_PORT", "8080"))

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set")
    client = weaviate.connect_to_local(
        host=host, port=port, headers={"X-Goog-Studio-Api-Key": api_key}
    )
    return client


def get_weaviate_store(client: WeaviateClient, collection_name: str):
    return WeaviateVectorStore(
        client=client,
        index_name=collection_name,
        embedding=embedding_function,
        text_key="text",
    )


def get_multi_vector_retriever(
    client: WeaviateClient, collection_name: str
) -> MultiVectorRetriever:
    vector_store = get_weaviate_store(client, collection_name)
    object_store = LocalFileStore(OBJECT_STORE_URL)
    id_key = "doc_id"

    return MultiVectorRetriever(
        vectorstore=vector_store,
        docstore=object_store,
        id_key=id_key,
    )
