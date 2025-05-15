from IPython.display import Image, display
from langchain_core.runnables.graph import MermaidDrawMethod

from api.ai_sre.agents import build_rag_graph

graph = build_rag_graph()
img = Image(
    graph.get_graph().draw_mermaid_png(
        draw_method=MermaidDrawMethod.API,
    )
)
with open("solution_graph.png", "wb") as png:
    png.write(img.data)
