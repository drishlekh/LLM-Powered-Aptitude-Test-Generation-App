

import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import AnyMessage
from langchain_tavily import TavilySearch
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool

load_dotenv()

# --- 1. Define Tools ---
tavily_tool = TavilySearch(max_results=1, api_key=os.environ.get("TAVILY_API_KEY")) # Get the single best result
tools = [tavily_tool]

# --- 2. Define Agent State ---
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    report_data: dict
    report_text: str

# --- 3. Define Graph Nodes ---
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1) 
llm_with_tools = llm.bind_tools(tools)

def planner_node(state: AgentState):
    prompt = f"""
You are an expert academic advisor. Your first job is to analyze a student's test data and decide which topics require external resources. You have one tool available: a web search tool.

**Student's Test Data:**
{state['report_data']}

Analyze the 'topic_breakdown'. Identify all topics where 'incorrect_count' is greater than 0. These are the student's weak topics.

For EACH weak topic you identify, you MUST use your web search tool (`tavily_search`):
1.  **To find a video tutorial:** Compulsorily frame your search query like this: `site:youtube.com "Time & Work" tutorial for placements.`
2.  **To find practice material:** Frame your search query like this: `free "Time & Work" practice questions GeeksforGeeks OR IndiaBIX`

After deciding on the tool calls, also write a preliminary analysis of the student's performance.
"""


    
    
    messages = [("user", prompt)]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

tool_node = ToolNode(tools)

# --- SUMMARIZER PROMPT ---
def summarizer_node(state: AgentState):
    """This node takes all information and generates the final, professional report."""
    
    
    prompt = f"""
You are a helpful career coach creating a final, polished performance report. Your task is to synthesize the information from the conversation history into a Markdown report.

**CRITICAL INSTRUCTION:** The conversation history contains `ToolMessage` results from a web search. Each result is a list containing a dictionary like `{{'url': 'THE_REAL_URL', 'content': 'THE_REAL_LINK_TEXT'}}`. You MUST use this exact data. **DO NOT invent, guess, or create your own URLs or link text.** You must extract the `url` and `content` directly from the tool messages.

**Your Task:**
Combine all information into a single, comprehensive, and professionally formatted report in Markdown. Follow this structure EXACTLY:

## Overall Summary
Write a brief, encouraging paragraph about the student's performance and potential.

## Detailed Analysis
### Your Strengths
*   List all the topics where the student performed well as bullet points.

### Areas for Improvement
*   List all the weak topics as bullet points.

## Personalized Recommendations
Write a short paragraph with actionable advice based on the analysis.

## Recommended Resources
For each weak topic, create a sub-heading. Then, find the corresponding `ToolMessage` in the history and construct the Markdown links using the real data you found.

### Topic: [Name of Weak Topic 1]
*   **Video Tutorial:** [Use the 'content' from the tool result](Use the 'url' from the tool result and the show the link too in clickable format)
*   **Practice Material:** [Use the 'content' from the tool result](Use the 'url' from the tool result)

Generate only the final report text in Markdown. Do not add any extra text or commentary.
"""
    response = llm.invoke(state["messages"] + [("user", prompt)])
    return {"report_text": response.content}

def should_continue(state: AgentState):
    if state["messages"][-1].tool_calls:
        return "use_tools"
    else:
        return "summarize"

# --- 4. Wire up the graph ---
graph = StateGraph(AgentState)
graph.add_node("planner", planner_node)
graph.add_node("tool_node", tool_node)
graph.add_node("summarizer", summarizer_node)
graph.set_entry_point("planner")
graph.add_conditional_edges("planner", should_continue, {"use_tools": "tool_node", "summarize": "summarizer"})
graph.add_edge("tool_node", "summarizer")
graph.add_edge("summarizer", END)
app_graph = graph.compile()

# --- 5. Create a wrapper function for Flask ---
def run_graph_agent(report_data_dict):
    try:
        initial_state = {"messages": [], "report_data": report_data_dict}
        final_state = app_graph.invoke(initial_state, {"recursion_limit": 5})
        return {"analysis": final_state.get('report_text', "Error: Could not generate report text.")}
    except Exception as e:
        return {"analysis": f"An error occurred while generating the report: {e}"}


# import os
# from dotenv import load_dotenv
# from typing import TypedDict, Annotated
# import operator
# from langchain_core.messages import AnyMessage
# from langchain_tavily import TavilySearch
# from langchain_groq import ChatGroq
# from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode
# from langchain_core.tools import tool

# load_dotenv()

# # --- 1. Define Tools ---
# tavily_tool = TavilySearch(max_results=1, api_key=os.environ.get("TAVILY_API_KEY"))
# tools = [tavily_tool]

# # --- 2. Define Agent State ---
# class AgentState(TypedDict):
#     messages: Annotated[list[AnyMessage], operator.add]
#     report_data: dict
#     report_text: str

# # --- 3. Define Graph Nodes ---
# llm = ChatGroq(model="llama3-8b-8192", temperature=0.1)
# llm_with_tools = llm.bind_tools(tools)

# def planner_node(state: AgentState):
#     prompt = f"""
# You are an expert academic advisor. Your first job is to analyze a student's test data and decide which topics require external resources. You have one tool available: a web search tool.

# **Student's Test Data:**
# {state['report_data']}

# Analyze the 'topic_breakdown'. Identify all topics where 'incorrect_count' is greater than 0. These are the student's weak topics.

# For EACH weak topic you identify, you MUST use your web search tool (`tavily_search`):
# 1.  **To find a video tutorial:** Frame your search query like this: `site:youtube.com "Time & Work" tutorial for placements`
# 2.  **To find practice material:** Frame your search query like this: `free "Time & Work" practice questions GeeksforGeeks OR IndiaBIX`

# After deciding on the tool calls, also write a preliminary analysis of the student's performance.
# """
#     messages = [("user", prompt)]
#     response = llm_with_tools.invoke(messages)
#     return {"messages": [response]}

# tool_node = ToolNode(tools)

# # --- FINAL, MOST ROBUST SUMMARIZER PROMPT ---
# # In agent.py, replace only this function:

# def summarizer_node(state: AgentState):
#     """This node takes all information and generates the final, professional report."""
    
#     # This is the final, most direct prompt to ensure correct hyperlink formatting.
#     prompt = f"""
# You are a report-generating AI. Your only task is to synthesize the provided conversation history into a final, well-formatted Markdown document.

# **CRITICAL FORMATTING INSTRUCTION:**
# You MUST create clickable Markdown hyperlinks for all resources. The tool's output for a search result looks like this: `{{'url': 'https://www.real-url.com/page', 'content': 'Title of the Page'}}`.
# You MUST convert this into the following Markdown format: `[Title of the Page](https://www.real-url.com/page)`

# **DO NOT** write the URL in plain text. **DO NOT** add parentheses around the URL without using the square brackets for the text. Follow the `[Text](URL)` syntax precisely.

# **Your Task:**
# Generate a report with the following structure, using the data from the conversation history and applying the critical formatting instruction above for all links.

# ## Overall Summary
# (Write a brief, encouraging paragraph here)

# ## Detailed Analysis
# ### Your Strengths
# *   (List the strong topics here)

# ### Areas for Improvement
# *   (List the weak topics here)

# ## Personalized Recommendations
# (Write a short paragraph with actionable advice here)

# ## Recommended Resources
# (For each weak topic, create a sub-heading and list the resources using the correct hyperlink format)

# ### Topic: [Name of Weak Topic 1]
# *   **Video Tutorial:** [Use the 'content' as text](Use the 'url' as the link)
# *   **Practice Material:** [Use the 'content' as text](Use the 'url' as the link)

# Generate only the final report text in Markdown.
# """
#     response = llm.invoke(state["messages"] + [("user", prompt)])
#     return {"report_text": response.content}

# def should_continue(state: AgentState):
#     if state["messages"][-1].tool_calls:
#         return "use_tools"
#     else:
#         return "summarize"

# # --- 4. Wire up the graph ---
# graph = StateGraph(AgentState)
# graph.add_node("planner", planner_node)
# graph.add_node("tool_node", tool_node)
# graph.add_node("summarizer", summarizer_node)
# graph.set_entry_point("planner")
# graph.add_conditional_edges("planner", should_continue, {"use_tools": "tool_node", "summarize": "summarizer"})
# graph.add_edge("tool_node", "summarizer")
# graph.add_edge("summarizer", END)
# app_graph = graph.compile()

# # --- 5. Create a wrapper function for Flask ---
# def run_graph_agent(report_data_dict):
#     try:
#         initial_state = {"messages": [], "report_data": report_data_dict}
#         final_state = app_graph.invoke(initial_state, {"recursion_limit": 5})
#         return {"analysis": final_state.get('report_text', "Error: Could not generate report text.")}
#     except Exception as e:
#         return {"analysis": f"An error occurred while generating the report: {e}"}