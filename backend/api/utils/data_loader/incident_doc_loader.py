import io
import base64

from langchain.storage import InMemoryStore
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from weaviate import WeaviateClient
from pdf2image import convert_from_path
from PIL import Image

from api.utils.logger import logger
from api.utils.id_generator import gen_document_id
from api.utils.vs_weaviate_utils import (
    get_weaviate_store,
)
from api.utils.llm_google_utils import llm
from api.utils.llm_prompts import image_summary_prompt


def create_doc_image(file_url: str):
    try:
        pdf_images = convert_from_path(file_url)
        if not pdf_images:
            return None

        total_height = sum([image.height for image in pdf_images])
        max_width = max([image.width for image in pdf_images])

        merged_img = Image.new("RGB", (max_width, total_height))
        y_offset = 0
        for image in pdf_images:
            merged_img.paste(image, (0, y_offset))
            y_offset += image.height
        buffer = io.BytesIO()
        merged_img.save(buffer, format="PNG")
        logger.info(f"Successfully create base64 image for PDF file {file_url}")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logger.exception(
            f"Failed to generate image for PDF document {file_url}: {e}"
        )
        raise


def gen_pdf_summary(pdf_url: str, image_base64: str) -> str:
    try:
        response = llm.invoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": image_summary_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ]
                )
            ]
        )
        summary = response.content
        logger.info(f"Successfully generated summary for PDF {pdf_url}")
        return summary
    except Exception as e:
        logger.exception(f"Failed to generated summary for PDF {pdf_url}: {e}")
        raise


class IncidentDocLoader:
    """Incident summary document loader, use LLM to summarize Incident summary document
    and put summary into vector DB, put original incident summary document in object store.
    Then later we can use multi-vector retrieval to load original incident summary document"""

    def __init__(
        self,
        object_store: InMemoryStore,
        client: WeaviateClient,
        summary_collection_name: str,
    ):
        self.object_store = object_store
        self.client = client
        self.summary_collection_name = summary_collection_name

    def load(self, file_url: str) -> bool:
        summary_vector_store = get_weaviate_store(
            self.client, self.summary_collection_name
        )
        try:
            image_base64 = create_doc_image(file_url)
            if not image_base64:
                logger.error(f"Failed to get image from PDF file {file_url}")
                return False
            summary = gen_pdf_summary(file_url, image_base64)
            if not summary:
                logger.error(f"Got empty summary from PDF file {file_url}")
                return False

            id_key = "doc_id"
            doc_id = gen_document_id()
            document = Document(
                page_content=summary,
                metadata={"source": "pdf_summary", "doc_id": doc_id},
            )
            multi_retriever = MultiVectorRetriever(
                vectorstore=summary_vector_store,
                docstore=self.object_store,
                id_key=id_key,
            )

            # Add image and summary into multi-vector retriever, later use summary to retrieve image then feed into LLM
            multi_retriever.vectorstore.add_documents([document])
            multi_retriever.docstore.mset([(doc_id, image_base64)])
        except Exception as e:
            logger.exception(
                f"Failed to load incident analysis file {file_url}: {e}"
            )
            return False

        return True
