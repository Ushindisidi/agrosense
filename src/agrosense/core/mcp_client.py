from typing import Any, Dict, Optional
from uuid import uuid4
from .schemas import MCPContext, SourceDocument, AssetType, IntentType, Severity 
import logging

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Model Context Protocol Client (In-Memory Implementation).
    Acts as a centralized, thread-safe (for single-process use) shared memory bus 
    for all agents, using the definitive MCPContext schema.
    """
    
    # Store contexts globally
    _contexts: Dict[str, MCPContext] = {}
    
    def __init__(self):
        """Initializes the client."""
        pass
    
    def generate_session_id(self) -> str:
        """Generates a new unique session ID."""
        return str(uuid4())

    def create_session(self, session_id: str, query: str, region: str) -> MCPContext:
        """Initialize a new session context with initial user data."""
        if session_id in self._contexts:
            return self._contexts[session_id]
        
        context = MCPContext(
            session_id=session_id,
            query=query,
            region=region
        )
        self._contexts[session_id] = context
        logger.info(f"MCP Session created: {session_id}")
        return context
    
    def get_context(self, session_id: str) -> Optional[MCPContext]:
        """Retrieve context for a session."""
        return self._contexts.get(session_id)
    
    def update_context(self, session_id: str, **kwargs) -> MCPContext:
        """Update specific fields in context, handling Pydantic/Enum conversions."""
        context = self.get_context(session_id)
        if not context:
            logger.error(f"Attempted to update non-existent session ID: {session_id}")
            raise ValueError(f"Session ID '{session_id}' not found.")
        
        for key, value in kwargs.items():
            if not hasattr(context, key):
                logger.warning(f"Attempted to update unknown key '{key}' in MCPContext.")
                continue

            # Handle Pydantic model/Enum conversions for robust updates
            if key == 'retrieved_context' and isinstance(value, list):
                validated_docs = [
                    SourceDocument(**doc) if isinstance(doc, dict) else doc 
                    for doc in value
                ]
                setattr(context, key, validated_docs)
            elif key == 'asset_type' and isinstance(value, str):
                setattr(context, key, AssetType(value.upper()))
            elif key == 'intent' and isinstance(value, str):
                try:
                    setattr(context, key, IntentType(value.lower()))
                except ValueError:
                    setattr(context, key, IntentType.GENERAL_ADVICE) 
            elif key == 'alert_severity' and isinstance(value, str):
                setattr(context, key, Severity(value.upper()))
            elif hasattr(context, key):
                setattr(context, key, value)
        
        self._contexts[session_id] = context
        return context

    def get_full_context_summary(self, session_id: str) -> str:
        """
        Get the full, clean context summary for an agent to use. 
        This is typically injected into the agent's prompt template.
        """
        context = self.get_context(session_id)
        if not context:
            return "No context found."
            
        # Generating the structured summary for the agent
        return f"""
--- MCP CONTEXT STATE (Session: {context.session_id}) ---
[INPUT] Query: {context.query}
[INPUT] Region: {context.region}
[ROUTING] Asset Type: {context.asset_type.value} | Specific Asset: {context.asset_name or 'N/A'} | Intent: {context.intent.value}
[KNOWLEDGE] Documents Retrieved: {len(context.retrieved_context)}
[ENVIRONMENTAL] Regional Data Keys: {list(context.regional_data.keys())}
[OUTPUT] Diagnosis Status: {'COMPLETE' if len(context.final_diagnosis) > 100 else 'PENDING'}
[ACTION] Alert Triggered: {context.alert_triggered} (Severity: {context.alert_severity.value if context.alert_severity else 'N/A'})
-----------------------------------------------------------
"""

    def get_context_for_task(self, session_id: str) -> Dict[str, Any]:
        """Returns the context as a dictionary suitable for injecting into task templates."""
        context = self.get_context(session_id)
        return context.model_dump(by_alias=True) if context else {}
    
    def clear_session(self, session_id: str):
        """Clear a session context."""
        if session_id in self._contexts:
            del self._contexts[session_id]