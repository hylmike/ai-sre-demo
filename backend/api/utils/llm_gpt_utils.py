"""All utils class and functions related to OpenAI GPT models"""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.01, max_tokens=8192)

embedding_function = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256)
