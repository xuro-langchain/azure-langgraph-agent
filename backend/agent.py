import random
import asyncio
from typing import Dict, Any, Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from backend.tools import get_user_profile, list_resource_groups, list_subscriptions



# Load environment variables
load_dotenv(override=True)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class GraphState(TypedDict):
    """
    State for the agent. Add tools to the state so we know which tools are available to the agent.
    """
    messages: Annotated[list[BaseMessage], add_messages]

tools = [get_user_profile, list_resource_groups, list_subscriptions]
tool_node = ToolNode(tools)

async def agent_node(state: GraphState, config: Dict[str, Any]) -> GraphState:
    """
    Main agent node that handles user requests and can access Microsoft Graph data.
    """
    user = config.get("configurable", {}).get("langgraph_auth_user")
    user_email = user.get('email', 'Unknown') if user else 'Not authenticated'
    display_name = user.get('display_name', 'Unknown') if user else 'Not authenticated'
    llm_with_tools = llm.bind_tools(tools)
    system_message = f"""
    You are a helpful calendar assistant that can access the user's Microsoft Graph data to provide insights and recommendations.
    You have the following tools to help you:
    - get_user_profile: Get the user's profile information from Microsoft Graph (displayName, email, jobTitle)
    - list_resource_groups: List all resource groups in an Azure subscription. User must specify the subscription ID.
    - list_subscriptions: List all Azure subscriptions the user has access to.
    
    You should always be polite and use the following information to personalize your interactions with your user:
    - Name: {display_name}
    - Email: {user_email}

    If a tool call result indicates that the user has no access to a resource even after consenting, apologize and tell the user they don't have access to that resource.
    """
    messages = [SystemMessage(content=system_message)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}

def should_continue(state: GraphState) -> str:
    """Check if we should continue to tools or end."""
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return END

def create_graph():
    """Create the agent graph for a React-based app."""
    
    # Create the graph
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    
    graph.add_edge(START, "agent")
    graph.add_edge("tools", "agent")
    
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END}
    )
    return graph.compile()
