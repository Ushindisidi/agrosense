from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_models import ChatOpenAI
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AgroSenseMemory:
    """
    Advanced conversation memory for agricultural advisory
    """
    
    def __init__(self, session_id: str, memory_type: str = "buffer"):
        """
        Initialize memory system
        
        Args:
            session_id: Unique session identifier
            memory_type: 'buffer' for full history or 'summary' for condensed
        """
        self.session_id = session_id
        self.memory_type = memory_type
        
        if memory_type == "summary":
            # Summary memory - condenses older messages
            try:
                llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
                self.memory = ConversationSummaryMemory(
                    llm=llm,
                    return_messages=True,
                    memory_key="chat_history"
                )
            except Exception as e:
                logger.warning(f"Failed to create summary memory: {e}. Using buffer.")
                self.memory = ConversationBufferMemory(
                    return_messages=True,
                    memory_key="chat_history"
                )
        else:
            # Buffer memory - keeps all messages
            self.memory = ConversationBufferMemory(
                return_messages=True,
                memory_key="chat_history",
                input_key="input",
                output_key="output"
            )
        
        # Track important context
        self.context = {
            "crop_type": None,
            "location": None,
            "problem_type": None,
            "previous_diagnoses": []
        }
    
    def add_user_message(self, message: str):
        """Add user message to memory"""
        try:
            self.memory.chat_memory.add_user_message(message)
            self._extract_context(message)
        except Exception as e:
            logger.error(f"Error adding user message: {e}")
    
    def add_ai_message(self, message: str):
        """Add AI response to memory"""
        try:
            self.memory.chat_memory.add_ai_message(message)
        except Exception as e:
            logger.error(f"Error adding AI message: {e}")
    
    def _extract_context(self, message: str):
        """Extract and update context from message"""
        message_lower = message.lower()
        
        # Detect crop types
        crops = ["maize", "wheat", "coffee", "tea", "potato", "tomato", "beans"]
        for crop in crops:
            if crop in message_lower:
                self.context["crop_type"] = crop
                break
        
        # Detect locations
        locations = ["nairobi", "mombasa", "kisumu", "nakuru", "eldoret", "meru"]
        for location in locations:
            if location in message_lower:
                self.context["location"] = location
                break
        
        # Detect problem types
        if any(word in message_lower for word in ["disease", "sick", "dying", "spots", "wilting"]):
            self.context["problem_type"] = "disease"
        elif any(word in message_lower for word in ["pest", "insects", "bugs", "eating"]):
            self.context["problem_type"] = "pest"
        elif any(word in message_lower for word in ["fertilizer", "nutrients", "yellow"]):
            self.context["problem_type"] = "nutrition"
    
    def get_history(self, last_n: Optional[int] = None) -> List[Dict[str, str]]:
        """Get conversation history"""
        try:
            messages = self.memory.chat_memory.messages
            
            if last_n:
                messages = messages[-last_n:]
            
            history = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    history.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    history.append({"role": "assistant", "content": msg.content})
                elif isinstance(msg, SystemMessage):
                    history.append({"role": "system", "content": msg.content})
            
            return history
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
    
    def get_context_summary(self) -> str:
        """Get summary of conversation context"""
        summary_parts = []
        
        if self.context["crop_type"]:
            summary_parts.append(f"Discussing: {self.context['crop_type']}")
        
        if self.context["location"]:
            summary_parts.append(f"Location: {self.context['location']}")
        
        if self.context["problem_type"]:
            summary_parts.append(f"Issue: {self.context['problem_type']}")
        
        if self.context["previous_diagnoses"]:
            summary_parts.append(f"Previous diagnoses: {len(self.context['previous_diagnoses'])}")
        
        return " | ".join(summary_parts) if summary_parts else "New conversation"
    
    def add_diagnosis(self, diagnosis: str):
        """Track diagnosis in context"""
        self.context["previous_diagnoses"].append({
            "diagnosis": diagnosis[:200],  # Store summary
            "timestamp": str(type(self).__name__)
        })
    
    def clear(self):
        """Clear conversation memory"""
        try:
            self.memory.clear()
            self.context = {
                "crop_type": None,
                "location": None,
                "problem_type": None,
                "previous_diagnoses": []
            }
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")
    
    def to_dict(self) -> Dict:
        """Export memory to dictionary"""
        return {
            "session_id": self.session_id,
            "memory_type": self.memory_type,
            "history": self.get_history(),
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgroSenseMemory':
        """Create memory from dictionary"""
        memory = cls(
            session_id=data["session_id"],
            memory_type=data.get("memory_type", "buffer")
        )
        
        # Restore history
        for msg in data.get("history", []):
            if msg["role"] == "user":
                memory.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                memory.add_ai_message(msg["content"])
        
        # Restore context
        memory.context = data.get("context", memory.context)
        
        return memory


# Memory manager for multiple sessions
class MemoryManager:
    """Manages memory for multiple concurrent sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, AgroSenseMemory] = {}
    
    def get_or_create(self, session_id: str, memory_type: str = "buffer") -> AgroSenseMemory:
        """Get existing memory or create new one"""
        if session_id not in self.sessions:
            self.sessions[session_id] = AgroSenseMemory(session_id, memory_type)
        return self.sessions[session_id]
    
    def delete(self, session_id: str):
        """Delete session memory"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def clear_all(self):
        """Clear all sessions"""
        self.sessions.clear()


# Global memory manager
memory_manager = MemoryManager()