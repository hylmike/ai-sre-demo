"""All until classes and functions related to Google LLM"""

from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", temperature=0.01, max_output_tokens=8192
)

embedding_function = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004"
)
