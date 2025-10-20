import os
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from src.agrosense.core.model_router import get_model_for_task, TaskType
from .core.mcp_client import MCPClient
from .tools.rag_tool import RAGTool
from .tools.weather_price_tool import WeatherPriceTool
from .tools.n8n_alert_tool import N8NAlertTool

# Load environment variables
load_dotenv()

@CrewBase
class AgroSenseCrew:
    """
    AgroSense Multi-Agent Crew
    Hierarchical agent system for precision agriculture analysis.
    """

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self):
        from pathlib import Path
        env_path = Path(__file__).parent.parent.parent / ".env"
        print(f"🔍 Checking .env: {env_path.exists()} at {env_path.absolute()}")

        load_dotenv(dotenv_path=env_path, override=True)

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or len(api_key) < 10:
            raise ValueError("❌ GOOGLE_API_KEY not loaded correctly!")
        print(f"✅ Google API Key loaded: {api_key[:10]}...")

        # Initialize MCP client and tools
        self.mcp_client = MCPClient()
        self.rag_tool = RAGTool(mcp_client=self.mcp_client)
        self.weather_price_tool = WeatherPriceTool(mcp_client=self.mcp_client)
        self.n8n_alert_tool = N8NAlertTool(mcp_client=self.mcp_client)

#agents
    @agent
    def orchestrator_agent(self) -> Agent:
        """Routes and classifies incoming user queries."""
        return Agent(
            config=self.agents_config['orchestrator_agent'],
            llm=get_model_for_task(TaskType.CLASSIFICATION, temperature=0.1),
            verbose=True
        )

    @agent
    def agri_knowledge_agent(self) -> Agent:
        """Retrieves contextual and domain knowledge from RAG system."""
        return Agent(
            config=self.agents_config['agri_knowledge_agent'],
            llm=get_model_for_task(TaskType.KNOWLEDGE_RETRIEVAL, temperature=0.2),
            tools=[self.rag_tool],
            verbose=True
        )

    @agent
    def weather_price_agent(self) -> Agent:
        """Fetches and integrates regional weather and market data."""
        return Agent(
            config=self.agents_config['weather_price_agent'],
            llm=get_model_for_task(TaskType.CONVERSATION, temperature=0.2),
            tools=[self.weather_price_tool],
            verbose=True
        )

    @agent
    def diagnostic_agent(self) -> Agent:
        """Generates structured diagnostic reports (multi-section format)."""
        return Agent(
            config=self.agents_config['diagnostic_agent'],
            llm=get_model_for_task(TaskType.DIAGNOSIS, temperature=0.3),
            verbose=True
        )

    @agent
    def action_agent(self) -> Agent:
        """Handles alert generation, formatting, and workflow automation."""
        return Agent(
            config=self.agents_config['action_agent'],
            llm=get_model_for_task(TaskType.ALERT_DECISION, temperature=0.0),
            tools=[self.n8n_alert_tool],
            verbose=True
        )

    # ----------------------------
    # 🧩 TASKS
    # ----------------------------

    @task
    def classify_query_task(self) -> Task:
        """Step 1: Classify the user’s agricultural query."""
        return Task(
            config=self.tasks_config['classify_query_task'],
            agent=self.orchestrator_agent(),
        )

    @task
    def retrieve_knowledge_task(self) -> Task:
        """Step 2: Retrieve knowledge based on the classified query."""
        return Task(
            config=self.tasks_config['retrieve_knowledge_task'],
            agent=self.agri_knowledge_agent(),
            context=[self.classify_query_task()],
        )

    @task
    def fetch_regional_data_task(self) -> Task:
        """Step 3: Pull weather and market data for regional context."""
        return Task(
            config=self.tasks_config['fetch_regional_data_task'],
            agent=self.weather_price_agent(),
            context=[self.classify_query_task()],
        )

    @task
    def generate_diagnosis_task(self) -> Task:
        """Step 4: Generate a full structured diagnosis and recommendations."""
        return Task(
            config=self.tasks_config['generate_diagnosis_task'],
            agent=self.diagnostic_agent(),
            context=[self.retrieve_knowledge_task(), self.fetch_regional_data_task()],
            output_file='final_diagnosis.txt'
        )

    @task
    def check_alerts_task(self) -> Task:
        """Step 5: Evaluate severity, trigger alerts, and format final output."""
        return Task(
            config=self.tasks_config['check_alerts_task'],
            agent=self.action_agent(),
            context=[self.generate_diagnosis_task()],
            output_file='alert_status.txt'
        )

    # ----------------------------
    # 🚀 CREW EXECUTION
    # ----------------------------

    @crew
    def crew(self) -> Crew:
        """Define and return the full AgroSense agent workflow."""
        tasks = [
            self.classify_query_task(),
            self.retrieve_knowledge_task(),
            self.fetch_regional_data_task(),
            self.generate_diagnosis_task(),
            self.check_alerts_task(),
        ]

        return Crew(
            agents=self.agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
            full_output=True,
        )
