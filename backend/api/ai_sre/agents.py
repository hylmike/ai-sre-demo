"""All agents used in chatbot DAG graph"""

from typing import TypedDict, Annotated
import operator
import base64

from langchain_core.agents import AgentAction
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langgraph.graph import StateGraph, END

from .models import RoleTypes
from api.utils.logger import logger
from api.utils.vs_weaviate_utils import (
    get_multi_vector_retriever,
    SUMMARY_COLLECTION_NAME,
)
from api.utils.llm_prompts import (
    query_translation_prompt_template,
    final_answer_prompt_template,
    central_processor_system_prompt,
    extract_info_from_images_prompt,
)
from api.utils.llm_gpt_utils import llm
from api.utils.vs_weaviate_utils import (
    get_weaviate_store,
    TEXT_COLLECTION_NAME,
    get_client,
)

MAX_RETRIEVAL_RESULTS = 10


class AgentState(TypedDict):
    """Agent state used for chatbot graph, will be maintained by agent"""

    query: str
    chat_history: list[str]
    inter_steps: Annotated[list[tuple[AgentAction, str]], operator.add]


def query_translation(query: str) -> list[str]:
    """Use LLM to improve query content and get multiple related queries"""

    prompt = ChatPromptTemplate.from_template(query_translation_prompt_template)
    chain = prompt | llm | StrOutputParser() | (lambda x: x.split("\n"))

    try:
        queries = chain.invoke({"query": query})
    except Exception as e:
        logger.error(f"Failed to get related queries from LLM: {e}")
        return [query]

    return queries


def multi_queries_retriever(queries: list[str]) -> list[str]:
    """Retrieve similar contents from vector store for all queries, each query retrieve topN results"""
    with get_client() as client:
        vector_store = get_weaviate_store(client, TEXT_COLLECTION_NAME)
        docs = []
        for query in queries:
            results = vector_store.similarity_search_with_score(
                query=query, k=3
            )
            for res, score in results:
                docs.append((score, res.page_content))
        docs.sort(key=lambda x: -x[0])
        final_results = set()
        for score, content in docs:
            if content not in final_results:
                final_results.add(content)
                if len(final_results) >= MAX_RETRIEVAL_RESULTS:
                    break

        return list(final_results)


@tool("query_relevant_engineering_documents")
def query_relevant_engineering_documents(query: str):
    """Search query related engineering guidelines from given vector store and return them"""

    enhanced_queries = query_translation(query)
    retrieved_context = ""
    try:
        retrieved_results = multi_queries_retriever(enhanced_queries)
    except Exception as e:
        logger.error(
            f"Failed to retrieve results from vector store for queries {enhanced_queries}: {e}"
        )
        return retrieved_context

    for result in retrieved_results:
        retrieved_context += f"{result}\n"
    return f"Data Source: Engineering documents\nRelated Information: {retrieved_context}\n"


@tool("query_relevant_incident_analysis_documents")
def query_relevant_incident_analysis_documents(query: str):
    """Retrieve query related summaries from vector database, then feed related incident analysis
    PDF document in images as context to LLM, to extract query related incident troubleshooting
    information from document and return it"""
    with get_client() as client:
        multi_retriever = get_multi_vector_retriever(
            client=client, collection_name=SUMMARY_COLLECTION_NAME
        )
        results = multi_retriever.invoke(query)
        if not results:
            return "Data source: incident analysis documents\nResult: No relevant information"
        image = base64.b64encode(results[0]).decode("utf-8")

        human_messages = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image}"},
            }
        ]
        messages = [
            (RoleTypes.SYSTEM, extract_info_from_images_prompt),
            (RoleTypes.HUMAN, human_messages),
        ]

        try:
            response = llm.invoke(messages)
            logger.info(
                f"Successfully extract information from images {response.content}"
            )
        except Exception as e:
            logger.error(
                f"Failed to retrieve information from images with LLM: {e}"
            )
            return "Data source: incident analysis documents\nResult: No relevant information"

        return response.content


@tool("query_relevant_historical_incidents")
def query_relevant_historical_incidents(query: str):
    """Find query related historical incidents from elastic search database"""
    return "Data source: historical incident records\nResult: No relevant information"


#     return """
# Data source: Historical incident query
# Incident title: Survey trending report returned 500 error
# Incident description: From DataDog found loading trends reports got 500 error returned, with no clear pattern related to specific report types or accounts. Overall trends report loading success rate from 99% to 78%.
# Root cause analysis: One backend container worked at abnormal status, then this caused most trends report requests failed at that container with 500 error. This led to big trends report loading success rate decreasing. After we reset that problematic container, the trends report loading success rate returned to normal.
# """


@tool("query_relevant_code_change_history")
def query_relevant_code_change_history(query: str):
    """Find query related code change history from GitHub"""
    return "Data source: code change history\nResult: No relevant information"


@tool("query_relevant_application_monitoring_data")
def query_relevant_application_monitoring_data(query: str):
    """Find query related application monitoring data from DataDog"""
    return "Data source: application monitoring data\nResult: No relevant information"


@tool("final_answer")
def final_answer(query: str, context: str) -> str:
    """Return a nature language response to the user, based on original user query and aggregated context \
    from all tools outputs, use LLM to get final answer for query"""

    try:
        prompt = ChatPromptTemplate.from_template(final_answer_prompt_template)
        chain = (
            {
                "query": RunnablePassthrough(),
                "context": RunnablePassthrough(),
            }
            | prompt
            | llm
            | StrOutputParser()
        )
        answer = chain.invoke({"query": query, "context": context})
        logger.info("Successfully get final answer with LLM")
    except Exception as e:
        logger.error(f"Failed to get final answer with LLM: {e}")
        return "Can't find answer"

    return answer


def create_scratchpad(inter_steps: list[AgentAction]):
    """Create scratchpad based on inter_steps from AgentState"""

    analysis_steps = []
    for action in inter_steps:
        if action.log != "TBD":
            analysis_steps.append(
                f"Tool: {action.tool}, input: {action.tool_input}\nOutput: {action.log}"
            )
    return "\n-----------\n".join(analysis_steps)


def router(state: AgentState) -> str:
    """return the tool name to use, if bad format got to final answer"""
    if isinstance(state["inter_steps"], list):
        return state["inter_steps"][-1].tool
    else:
        logger.info("Invalid route format")
        return "final_answer"


def run_tool(state: AgentState):
    """Run tool node based on last state value"""
    tool_str_to_function = {
        "query_relevant_engineering_documents": query_relevant_engineering_documents,
        "query_relevant_incident_analysis_documents": query_relevant_incident_analysis_documents,
        "query_relevant_historical_incidents": query_relevant_historical_incidents,
        "query_relevant_code_change_history": query_relevant_code_change_history,
        "query_relevant_application_monitoring_data": query_relevant_application_monitoring_data,
        "final_answer": final_answer,
    }

    tool_name = state["inter_steps"][-1].tool
    tool_args = state["inter_steps"][-1].tool_input

    response = tool_str_to_function[tool_name].invoke(input=tool_args)
    action_output = AgentAction(
        tool=tool_name, tool_input=tool_args, log=str(response)
    )
    return {"inter_steps": [action_output]}


def build_rag_graph():
    """Build adaptive RAG graph with all agent tools"""

    tools = [
        query_relevant_engineering_documents,
        query_relevant_incident_analysis_documents,
        query_relevant_historical_incidents,
        query_relevant_code_change_history,
        query_relevant_application_monitoring_data,
        final_answer,
    ]
    processor_prompt = ChatPromptTemplate.from_messages(
        [
            (RoleTypes.SYSTEM, central_processor_system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            (RoleTypes.HUMAN, "{query}"),
            (RoleTypes.AI, "scratchpad: {scratchpad}"),
        ]
    )
    processor_chain = (
        {
            "query": lambda x: x["query"],
            "chat_history": lambda x: x["chat_history"],
            "scratchpad": lambda x: create_scratchpad(
                inter_steps=x["inter_steps"]
            ),
        }
        | processor_prompt
        | llm.bind_tools(tools, tool_choice="any")
    )

    # Define the run central process function
    def run_processor(state: AgentState):
        logger.info("run processor")
        logger.info(f"inter_steps: {state['inter_steps']}")
        response = processor_chain.invoke(state)
        tool_name = response.tool_calls[0]["name"]
        tool_args = response.tool_calls[0]["args"]
        action_output = AgentAction(
            tool=tool_name, tool_input=tool_args, log="TBD"
        )

        logger.info(f"Next tool: {tool_name}, tool input: {tool_args}")
        return {"inter_steps": [action_output]}

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("processor", run_processor)
    graph_builder.add_node("query_relevant_engineering_documents", run_tool)
    graph_builder.add_node(
        "query_relevant_incident_analysis_documents", run_tool
    )
    graph_builder.add_node("query_relevant_historical_incidents", run_tool)
    graph_builder.add_node("query_relevant_code_change_history", run_tool)
    graph_builder.add_node(
        "query_relevant_application_monitoring_data", run_tool
    )
    graph_builder.add_node("final_answer", run_tool)
    graph_builder.set_entry_point("processor")
    graph_builder.add_conditional_edges(source="processor", path=router)
    for tool_object in tools:
        if tool_object.name != "final_answer":
            graph_builder.add_edge(tool_object.name, "processor")
    graph_builder.add_edge("final_answer", END)

    graph = graph_builder.compile()
    return graph
