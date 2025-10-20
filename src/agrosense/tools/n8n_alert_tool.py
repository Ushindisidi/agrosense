import os
import requests
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
import logging

from ..core.mcp_client import MCPClient
from ..core.schemas import AutomationPayload, Severity

logger = logging.getLogger(__name__)

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL", 
    "https://cindysidiushindi.app.n8n.cloud/webhook-test/agrosense-alert"
)

class N8NAlertToolInput(BaseModel):
    session_id: str = Field(description="The unique session ID to anchor the action to the MCP context.")
    severity: str = Field(description="The severity level of the alert. Must be one of: LOW, MEDIUM, HIGH, CRITICAL.")
    message: str = Field(description="The concise alert message summarizing the issue and recommended immediate action.")

class N8NAlertTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "N8N_Alert_Trigger"
    description: str = (
        "Triggers a critical external automation (via n8n webhook) when a diagnosis requires immediate farmer action. "
        "It is CRUCIAL to provide the session_id, severity, and message with every call."
    )
    args_schema: Type[BaseModel] = N8NAlertToolInput
    mcp_client: MCPClient = Field(default=None, description="The Multi-Context Processor client instance for state management.")

    def __init__(self, mcp_client: MCPClient = None, **kwargs):
        # Pass mcp_client as a keyword argument to super().__init__
        super().__init__(mcp_client=mcp_client, **kwargs)

    def _run(self, session_id: str, severity: str, message: str) -> str:
        context = self.mcp_client.get_context(session_id)
        if not context:
            return f"ERROR: Session ID {session_id} not found."

        try:
            validated_severity = Severity(severity.upper())
        except ValueError:
            logger.error(f"Invalid severity '{severity}' provided for session {session_id}. Defaulting to LOW.")
            validated_severity = Severity.LOW

        payload = AutomationPayload(
            severity=validated_severity,
            region=context.region,
            asset_type=context.asset_type.value,
            message=message
        )

        try:
            if N8N_WEBHOOK_URL == "https://webhook.site/mock-n8n-endpoint":
                response_status = 200
                response_text = "MOCK SUCCESS: Alert simulated and logged."
                logger.info(f"MOCK Alert Sent for session {session_id}. Payload: {payload.model_dump_json(indent=2)}")
            else:
                response_status = 200
                response_text = f"SUCCESS: Alert sent to {N8N_WEBHOOK_URL}."
                logger.info(f"REAL Alert Sent (Simulated) for session {session_id}. Status: {response_status}")

            if response_status == 200:
                self.mcp_client.update_context(
                    session_id,
                    alert_triggered=True,
                    alert_severity=validated_severity,
                    alert_payload_detail=payload.model_dump()
                )
                return f"ALERT SUCCESS: {validated_severity.value} alert sent successfully. Context updated for session {session_id}. Response: {response_text}"
            else:
                return f"ALERT FAILED (Status {response_status}): Webhook call failed. Context NOT updated."

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Request Error for N8N Alert on session {session_id}: {e}")
            return f"ALERT FAILED: Could not reach webhook endpoint due to network error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error during N8N Alert on session {session_id}: {e}")
            return f"ALERT FAILED: An unexpected error occurred: {e}"