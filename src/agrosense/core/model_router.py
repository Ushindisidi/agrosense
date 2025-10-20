from enum import Enum
from typing import Dict, Any, Optional, List
from crewai import LLM
import os
import logging

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    GEMINI = "gemini"
    COHERE = "cohere"
    GROQ = "groq"


class ModelTier(Enum):
    """Model capability tiers"""
    FAST = "fast"  # Quick responses, simple tasks
    BALANCED = "balanced"  # Balance of speed and quality
    POWERFUL = "powerful"  # Complex reasoning, high quality


class TaskType(Enum):
    """Types of tasks for intelligent routing"""
    CLASSIFICATION = "classification"
    CONVERSATION = "conversation"
    DIAGNOSIS = "diagnosis"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    ALERT_DECISION = "alert_decision"


class ModelRouter:
    """
    Intelligent model selection with fallback mechanisms
    Uses only free/affordable providers
    """
    
    # Model configurations by tier
    MODEL_CONFIG = {
        ModelTier.FAST: [
            {"provider": ModelProvider.GROQ, "model": "groq/llama-3.3-70b-versatile", "temp": 0.5},
            {"provider": ModelProvider.GEMINI, "model": "gemini/gemini-2.0-flash", "temp": 0.3},
            {"provider": ModelProvider.COHERE, "model": "command-r", "temp": 0.3},
        ],
        ModelTier.BALANCED: [
            {"provider": ModelProvider.COHERE, "model": "command-r-plus", "temp": 0.5},
            {"provider": ModelProvider.GROQ, "model": "groq/llama-3.3-70b-versatile", "temp": 0.5},
            {"provider": ModelProvider.GEMINI, "model": "gemini/gemini-2.0-flash", "temp": 0.5},
        ],
        ModelTier.POWERFUL: [
            {"provider": ModelProvider.COHERE, "model": "command-r-plus", "temp": 0.5},
            {"provider": ModelProvider.GEMINI, "model": "gemini/gemini-2.0-flash", "temp": 0.7},
            {"provider": ModelProvider.GROQ, "model": "groq/llama-3.3-70b-versatile", "temp": 0.7},
        ]
    }
    
    # Task-to-tier mapping
    TASK_TIER_MAP = {
        TaskType.CLASSIFICATION: ModelTier.FAST,
        TaskType.CONVERSATION: ModelTier.FAST,
        TaskType.DIAGNOSIS: ModelTier.POWERFUL,
        TaskType.KNOWLEDGE_RETRIEVAL: ModelTier.BALANCED,
        TaskType.ALERT_DECISION: ModelTier.FAST,
    }
    
    def __init__(self):
        self.api_keys = {
            ModelProvider.GEMINI: os.getenv("GOOGLE_API_KEY"),
            ModelProvider.COHERE: os.getenv("COHERE_API_KEY"),
            ModelProvider.GROQ: os.getenv("GROQ_API_KEY"),
        }
        
        # Track failures for adaptive fallback
        self.failure_count = {provider: 0 for provider in ModelProvider}
        self.max_failures = 3
    
    def get_llm(
        self,
        task_type: TaskType,
        tier_override: Optional[ModelTier] = None,
        temperature_override: Optional[float] = None
    ) -> LLM:
        """
        Get appropriate LLM for task with intelligent fallback
        
        Args:
            task_type: Type of task to perform
            tier_override: Force specific tier (optional)
            temperature_override: Override default temperature
            
        Returns:
            Configured LLM instance
        """
        tier = tier_override or self.TASK_TIER_MAP.get(task_type, ModelTier.BALANCED)
        models = self.MODEL_CONFIG[tier]
        
        # Try models in order until one works
        for model_config in models:
            provider = model_config["provider"]
            
            # Skip if provider has too many failures
            if self.failure_count[provider] >= self.max_failures:
                logger.warning(f"Skipping {provider.value} due to repeated failures")
                continue
            
            # Check if API key available
            if not self.api_keys.get(provider):
                logger.warning(f"No API key for {provider.value}")
                continue
            
            try:
                temperature = temperature_override or model_config["temp"]
                
                llm = LLM(
                    model=model_config["model"],
                    temperature=temperature,
                    api_key=self.api_keys[provider]
                )

                logger.info(f"[INFO] Using {provider.value}: {model_config['model']}")
                return llm
                
            except Exception as e:
                self.failure_count[provider] += 1
                logger.error(f"[ERROR] Failed to initialize {provider.value}: {e}")
                continue
        
        # Ultimate fallback - use any available provider
        return self._emergency_fallback()
    
    def _emergency_fallback(self) -> LLM:
        """Emergency fallback to any working provider"""
        for provider, api_key in self.api_keys.items():
            if api_key and self.failure_count[provider] < self.max_failures:
                try:
                    # Use simplest/fastest model as fallback
                    if provider == ModelProvider.GEMINI:
                        return LLM(
                            model="gemini/gemini-2.0-flash-exp",
                            temperature=0.5,
                            api_key=api_key
                        )
                    elif provider == ModelProvider.GROQ:
                        return LLM(
                            model="groq/llama-3.3-70b-versatile",
                            temperature=0.5,
                            api_key=api_key
                        )
                    elif provider == ModelProvider.COHERE:
                        return LLM(
                            model="command-r",
                            temperature=0.5,
                            api_key=api_key
                        )
                except Exception as e:
                    logger.error(f"Emergency fallback failed for {provider.value}: {e}")
                    continue
        
        raise RuntimeError("All AI providers failed. Please check API keys and service status.")
    
    def reset_failures(self, provider: Optional[ModelProvider] = None):
        """Reset failure counts"""
        if provider:
            self.failure_count[provider] = 0
        else:
            self.failure_count = {p: 0 for p in ModelProvider}
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        return {
            provider.value: {
                "available": bool(self.api_keys.get(provider)),
                "failures": self.failure_count[provider],
                "healthy": self.failure_count[provider] < self.max_failures
            }
            for provider in ModelProvider
        }


# Global router instance
model_router = ModelRouter()


def get_model_for_task(
    task_type: TaskType,
    tier: Optional[ModelTier] = None,
    temperature: Optional[float] = None
) -> LLM:
    """Convenience function to get model"""
    return model_router.get_llm(task_type, tier, temperature)