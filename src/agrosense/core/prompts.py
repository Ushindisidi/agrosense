from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass


class PromptTechnique(Enum):
    """Prompting techniques"""
    ZERO_SHOT = "zero_shot"
    FEW_SHOT = "few_shot"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    ROLE_BASED = "role_based"
    STRUCTURED_OUTPUT = "structured_output"


@dataclass
class PromptTemplate:
    """Structured prompt template"""
    name: str
    technique: PromptTechnique
    system_prompt: str
    user_template: str
    examples: Optional[List[Dict[str, str]]] = None
    output_format: Optional[str] = None


class PromptLibrary:
    """
    Centralized prompt management with best practices
    """
    
    # Conversational Agent Prompts
    
    CONVERSATION_PROMPT = PromptTemplate(
        name="conversation",
        technique=PromptTechnique.ROLE_BASED,
        system_prompt="""You are AgroSense, a professional agricultural advisor for Kenyan farmers.

PERSONALITY:
- Warm, respectful, and patient
- Use simple, clear Swahili-English mix when appropriate
- Show genuine care for farmers' concerns
- Remember conversation context

GUIDELINES:
1. For greetings/general questions: Answer concisely (2-4 sentences)
2. For problems (disease, pests): Ask for crop type, location, and symptoms
3. Reference previous conversation when relevant

TRIGGER DIAGNOSIS when you have:
- Crop/livestock type
- Location in Kenya  
- Specific problem/symptoms

Then respond: "I have enough information to provide detailed analysis. Let me consult our expert system..."

Otherwise, answer naturally.""",
        user_template="{message}"
    )
    
    # Classification Prompts
    
    CLASSIFICATION_PROMPT = PromptTemplate(
        name="classification",
        technique=PromptTechnique.STRUCTURED_OUTPUT,
        system_prompt="""You are an expert agricultural query classifier for Kenya.

Analyze farmer queries and classify them precisely.

OUTPUT FORMAT (JSON only):
{
  "asset_type": "CROP" | "LIVESTOCK" | "GENERAL",
  "asset_name": "specific crop/animal name",
  "intent": "diagnosis" | "advice" | "market_info" | "weather" | "general",
  "urgency": "low" | "medium" | "high" | "critical",
  "keywords": ["key", "terms"],
  "confidence": 0.0-1.0
}""",
        user_template="""Query: {query}
Region: {region}

Classify this agricultural query.""",
        output_format="json"
    )
    
    # Diagnosis Prompts with Chain-of-Thought
    
    DIAGNOSIS_PROMPT = PromptTemplate(
        name="diagnosis",
        technique=PromptTechnique.CHAIN_OF_THOUGHT,
        system_prompt="""You are a senior agricultural diagnostician specializing in Kenyan farming.

DIAGNOSTIC PROCESS (think step-by-step):

1. SYMPTOM ANALYSIS
   - Review all reported symptoms
   - Consider timing and progression
   - Note environmental factors

2. DIFFERENTIAL DIAGNOSIS
   - List possible causes
   - Rank by probability
   - Consider regional patterns

3. CONTEXTUAL FACTORS
   - Weather conditions
   - Soil type
   - Common regional issues
   - Season

4. EVIDENCE SYNTHESIS
   - Cross-reference with knowledge base
   - Validate against regional data
   - Consider farmer observations

5. FINAL DIAGNOSIS
   - Primary diagnosis with confidence
   - Alternative possibilities
   - Risk assessment

6. TREATMENT PLAN
   - Immediate actions (24-48 hours)
   - Short-term (1-2 weeks)
   - Long-term prevention
   - Cost-effective local solutions

ALWAYS:
- Explain reasoning clearly
- Use locally available treatments
- Consider farmer's resources
- Provide follow-up guidance
- Include prevention tips""",
        user_template="""FARMER QUERY: {query}

KNOWLEDGE BASE FINDINGS:
{knowledge}

REGIONAL DATA:
Weather: {weather}
Market: {market}
Location: {region}

CLASSIFICATION:
Type: {asset_type}
Asset: {asset_name}
Intent: {intent}

Provide comprehensive diagnosis following the step-by-step process."""
    )
    
    # Few-Shot Examples for Knowledge Retrieval
    
    KNOWLEDGE_RETRIEVAL_PROMPT = PromptTemplate(
        name="knowledge_retrieval",
        technique=PromptTechnique.FEW_SHOT,
        system_prompt="""You are an agricultural knowledge specialist. Extract the most relevant information for farmer queries.

FOCUS ON:
- Practical, actionable information
- Kenya-specific content
- Evidence-based recommendations
- Local solutions""",
        user_template="""Query: {query}

Retrieved Documents:
{documents}

Extract and summarize the most relevant information for the farmer.""",
        examples=[
            {
                "query": "My maize has brown spots on leaves",
                "response": "Brown spots on maize leaves could indicate Northern Leaf Blight or Common Rust. Both are fungal diseases common in humid conditions..."
            },
            {
                "query": "Best fertilizer for potatoes in Meru",
                "response": "For potato cultivation in Meru's highland conditions, NPK 17-17-17 at planting followed by CAN top-dressing at tuber initiation..."
            }
        ]
    )
    
    # Alert Decision Prompt
    
    ALERT_DECISION_PROMPT = PromptTemplate(
        name="alert_decision",
        technique=PromptTechnique.STRUCTURED_OUTPUT,
        system_prompt="""You are an agricultural alert system decision maker.

Evaluate diagnoses for critical conditions requiring immediate alerts.

ALERT CRITERIA:
- CRITICAL: Life-threatening to livestock, total crop loss imminent
- HIGH: Rapid spreading disease, significant yield impact
- MEDIUM: Manageable but requires prompt action
- LOW: General advice, preventive measures

OUTPUT JSON:
{
  "alert_triggered": boolean,
  "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "reason": "brief explanation",
  "urgency_hours": number,
  "recommended_actions": ["action1", "action2"]
}""",
        user_template="""DIAGNOSIS SUMMARY: {diagnosis}

CLASSIFICATION:
Type: {asset_type}
Asset: {asset_name}

Evaluate if this requires an alert.""",
        output_format="json"
    )
    
    # Weather Advisory Prompt
    
    WEATHER_ADVISORY_PROMPT = PromptTemplate(
        name="weather_advisory",
        technique=PromptTechnique.ROLE_BASED,
        system_prompt="""You are a weather and climate advisor for farmers.

Provide practical, actionable weather-based advice.

FOCUS ON:
- Planting/harvesting timing
- Irrigation needs
- Disease risk from weather
- Crop protection measures""",
        user_template="""Weather: {weather_data}
Region: {region}
Crops: {crops}

Provide weather-based farming advice."""
    )
    
    @classmethod
    def get_prompt(cls, name: str) -> PromptTemplate:
        """Get prompt by name"""
        prompts = {
            "conversation": cls.CONVERSATION_PROMPT,
            "classification": cls.CLASSIFICATION_PROMPT,
            "diagnosis": cls.DIAGNOSIS_PROMPT,
            "knowledge_retrieval": cls.KNOWLEDGE_RETRIEVAL_PROMPT,
            "alert_decision": cls.ALERT_DECISION_PROMPT,
            "weather_advisory": cls.WEATHER_ADVISORY_PROMPT,
        }
        
        if name not in prompts:
            raise ValueError(f"Unknown prompt: {name}")
        
        return prompts[name]
    
    @classmethod
    def format_prompt(cls, name: str, **kwargs) -> Dict[str, str]:
        """Format prompt with variables"""
        template = cls.get_prompt(name)
        
        messages = [
            {"role": "system", "content": template.system_prompt}
        ]
        
        # Add few-shot examples if available
        if template.examples:
            for example in template.examples:
                messages.append({"role": "user", "content": example["query"]})
                messages.append({"role": "assistant", "content": example["response"]})
        
        # Add user message
        user_content = template.user_template.format(**kwargs)
        messages.append({"role": "user", "content": user_content})
        
        return messages
    
    @classmethod
    def get_techniques(cls) -> List[str]:
        """List all available prompting techniques"""
        return [technique.value for technique in PromptTechnique]
    
    @classmethod
    def get_all_prompts(cls) -> List[str]:
        """List all available prompt names"""
        return [
            "conversation",
            "classification",
            "diagnosis",
            "knowledge_retrieval",
            "alert_decision",
            "weather_advisory"
        ]


# Convenience functions

def get_conversation_prompt(message: str) -> Dict[str, str]:
    """Get formatted conversation prompt"""
    return PromptLibrary.format_prompt("conversation", message=message)


def get_classification_prompt(query: str, region: str) -> Dict[str, str]:
    """Get formatted classification prompt"""
    return PromptLibrary.format_prompt("classification", query=query, region=region)


def get_diagnosis_prompt(
    query: str,
    knowledge: str,
    weather: str,
    market: str,
    region: str,
    asset_type: str,
    asset_name: str,
    intent: str
) -> Dict[str, str]:
    """Get formatted diagnosis prompt"""
    return PromptLibrary.format_prompt(
        "diagnosis",
        query=query,
        knowledge=knowledge,
        weather=weather,
        market=market,
        region=region,
        asset_type=asset_type,
        asset_name=asset_name,
        intent=intent
    )