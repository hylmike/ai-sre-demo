"""Load PDF file, chunk, indexing and save them into vector database, later used for information retrieval"""

from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from weaviate import WeaviateClient

from api.utils.vs_weaviate_utils import get_weaviate_store
from api.utils.logger import logger

class PDFLoader:
    """PDF file loader, load PDF file contents into vector DB"""

    def __init__(self, client: WeaviateClient, collection_name: str):
        self.client = client
        self.collection_name = collection_name

    async def load(self, file_url: str) -> bool:
        vector_store = get_weaviate_store(self.client, self.collection_name)
        try:
            loader = PyMuPDFLoader(
                file_path=file_url,
                mode="page",
                extract_tables="markdown",
            )
            raw_docs =loader.load()
            logger.info(f"Load {len(raw_docs)} pages from pdf file {file_url}")

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50, separators=["\n", "."])
            docs = text_splitter.split_documents(raw_docs)

            await vector_store.aadd_documents(
                documents=docs,
            )
            logger.info(f"Successfully loaded pdf file {file_url} in to vector DB")
            return True
        except Exception as e:
            logger.exception(f"Failed to load pdf file {file_url} in to vector DB: {e}")
            return False

    async def load_files(self, files: list[str]):
        for file_url in files:
            await self.load(file_url)




