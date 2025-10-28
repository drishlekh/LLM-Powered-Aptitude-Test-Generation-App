

***

# Report Generator for LLM Based MCQ Generator

This web application provides users with a dynamic quiz experience and generates a detailed, AI-powered performance report to help them identify strengths, weaknesses, and find relevant learning resources.

## Features

- **Dynamic Quiz Generation:** Creates customized quizzes based on user-selected subjects (Logical Reasoning, Quantitative Aptitude, Verbal Ability), difficulty, and number of questions using the Groq API for fast, on-the-fly generation.
- **Interactive Quiz Interface:** A modern, single-page quiz experience with a question palette for easy navigation, real-time answer checking, and a countdown timer for timed tests.
- **AI Agent for Performance Analysis:** After the quiz, an autonomous agent built with **LangGraph** analyzes the user's performance data.
- **Automated Resource Discovery:** The agent uses the **Tavily Search API** to automatically find relevant YouTube tutorials and practice materials for the user's specific weak topics.
- **Personalized Reporting:** The agent synthesizes its findings into a comprehensive, professional report that includes:
  - An overall performance summary.
  - A clear breakdown of strong and weak topics.
  - Actionable recommendations.
  - Clickable links to the learning resources it discovered.
- **PDF Export:** Users can download their personalized report as a PDF directly from the report page.

## Tech Stack & Core Services

- **Backend:** Flask, Python
- **AI Agent Framework:** LangGraph
- **LLM Provider:** Groq API (Llama 3 8B)
- **Web Search Tool:** Tavily Search API
- **Frontend:** HTML, Tailwind CSS, JavaScript
- **PDF Generation:** jsPDF, html2canvas (Client-Side)

## How It Works

1.  **Quiz Setup:** The user configures their desired quiz on the main page.
2.  **Test Session:** The user takes the quiz, and their answers are recorded.
3.  **Report Trigger:** Upon finishing, the user can click "Generate Detailed Report."
4.  **Agent Invocation:** The Flask backend sends the user's performance data to the LangGraph agent.
5.  **Agent Workflow:**
    - **Plan:** The agent analyzes the data to identify weak topics.
    - **Act:** It uses the Tavily API to search for learning resources for each weak topic.
    - **Summarize:** It combines its analysis and the search results into a final, formatted Markdown report.
6.  **Display:** The backend converts the Markdown to HTML and displays the final, polished report to the user.
