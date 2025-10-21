from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
import logging
import os
import json
from datetime import datetime, timedelta
import hashlib
import secrets
from collections import defaultdict
import redis
import gc
import os

# Memory optimizations for deployment
os.environ["TOKENIZERS_PARALLELISM"] = "false"
gc.set_threshold(700, 10, 10)  

from src.agrosense.crew import AgroSenseCrew
from src.agrosense.core.model_router import get_model_for_task, TaskType, model_router
from src.agrosense.core.prompts import PromptLibrary
from src.agrosense.core.langchain_memory import memory_manager

import sys
import codecs

if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors='replace')
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, errors='replace')

# Setup logging with rotation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agrosense.log'),
        logging.StreamHandler()
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="AgroSense API",
    description="Conversational Agricultural Advisory System with Free AI Providers",
    version="2.2.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None
)

# CORS middleware with security
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)

# Initialize Redis for session persistence (fallback to memory)
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    logger.info("[OK] Connected to Redis for persistent memory")
    USE_REDIS = True
except:
    logger.warning("[WARN] Redis unavailable. Using in-memory storage (sessions will be lost on restart)")
    USE_REDIS = False

# In-memory fallback
sessions: Dict[str, Dict[str, Any]] = {}
rate_limit_storage: Dict[str, List[datetime]] = defaultdict(list)

# Initialize crew (singleton)
crew_instance = None
conversational_llm = None

# Security: Rate limiting configuration
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60  # seconds
MAX_MESSAGE_LENGTH = 2000
MAX_SESSION_MESSAGES = 100
SESSION_TTL = 3600  # 1 hour


# Security Functions

def get_client_ip(request: Request) -> str:
    """Get client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    now = datetime.now()
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    
    # Clean old requests
    rate_limit_storage[client_ip] = [
        req_time for req_time in rate_limit_storage[client_ip]
        if req_time > cutoff
    ]
    
    # Check limit
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    rate_limit_storage[client_ip].append(now)
    return True


def sanitize_input(text: str) -> str:
    """Sanitize user input"""
    # Remove potential script injections
    dangerous_patterns = ["<script", "javascript:", "onerror=", "onclick="]
    sanitized = text
    for pattern in dangerous_patterns:
        sanitized = sanitized.replace(pattern, "")
    return sanitized.strip()


def generate_session_id() -> str:
    """Generate secure session ID"""
    return secrets.token_urlsafe(32)


# Session Management with Redis/Memory fallback

def save_session(session_id: str, data: Dict[str, Any]):
    """Save session with fallback"""
    try:
        if USE_REDIS:
            redis_client.setex(
                f"session:{session_id}",
                SESSION_TTL,
                json.dumps(data, default=str)
            )
        else:
            sessions[session_id] = data
    except Exception as e:
        logger.error(f"Error saving session: {e}")
        sessions[session_id] = data


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session with fallback"""
    try:
        if USE_REDIS:
            data = redis_client.get(f"session:{session_id}")
            return json.loads(data) if data else None
        else:
            return sessions.get(session_id)
    except Exception as e:
        logger.error(f"Error retrieving session: {e}")
        return sessions.get(session_id)


def delete_session(session_id: str):
    """Delete session"""
    try:
        if USE_REDIS:
            redis_client.delete(f"session:{session_id}")
        sessions.pop(session_id, None)
    except Exception as e:
        logger.error(f"Error deleting session: {e}")


def get_crew():
    """Get or create crew instance with error handling"""
    global crew_instance
    if crew_instance is None:
        try:
            logger.info("[FARM] Initializing AgroSense Crew...")
            crew_instance = AgroSenseCrew()
            logger.info("[OK] Crew initialized successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize crew: {e}")
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again later."
            )
    return crew_instance


def get_conversational_llm():
    """Get LLM with automatic fallback using model router"""
    global conversational_llm
    if conversational_llm is None:
        try:
            # Using model router for intelligent selection and automatic fallback
            # Tries Gemini → Groq → Cohere based on availability
            conversational_llm = get_model_for_task(
                task_type=TaskType.CONVERSATION,
                temperature=0.7
            )
            logger.info("[OK] Conversational LLM initialized with model router")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable"
            )
    return conversational_llm


# Request/Response Models with Validation

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    session_id: Optional[str] = None
    farmer_id: Optional[str] = None
    
    @validator('message')
    def sanitize_message(cls, v):
        return sanitize_input(v)


class ChatResponse(BaseModel):
    message: str
    session_id: str
    requires_action: bool = False
    action_type: Optional[str] = None
    classification: Optional[dict] = None
    alert_triggered: bool = False
    alert_severity: Optional[str] = None


class WeatherResponse(BaseModel):
    temperature: float
    humidity: float
    condition: str
    market_price: str


# Error Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global error handler with logging"""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Our team has been notified.",
            "type": "internal_error"
        }
    )


# Helper Functions with Memory

async def generate_conversational_response(
    message: str, 
    session_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate response with conversation memory using Prompt Library"""
    
    try:
        llm = get_conversational_llm()
        
        #  Using prompt library 
        messages = PromptLibrary.format_prompt(
            "conversation",
            message=message
        )
        
        #  Adding conversation history from memory if available
        if session_data and "messages" in session_data:
            # Insert history after system prompt but before current message
            history = []
            for msg in session_data["messages"][-10:]:
                history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Rebuild messages: system + history + current
            messages = [messages[0]] + history + [messages[-1]]
        
        response = llm.call(messages)
        ai_message = response if isinstance(response, str) else str(response)
        
        # Check readiness
        ready_keywords = [
            "detailed analysis",
            "expert system",
            "comprehensive recommendations",
            "detailed recommendations"
        ]
        
        is_ready = any(keyword.lower() in ai_message.lower() for keyword in ready_keywords)
        
        return {
            "message": ai_message,
            "is_ready_for_diagnosis": is_ready
        }
        
    except Exception as e:
        logger.error(f"Conversation error: {e}")
        # Fallback response
        return {
            "message": "I apologize, I'm experiencing technical difficulties. Please try rephrasing your question or contact support if the issue persists.",
            "is_ready_for_diagnosis": False
        }


async def extract_information(messages: list) -> Dict[str, Any]:
    """Extract information with fallback"""
    try:
        llm = get_conversational_llm()
        
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" for msg in messages[-10:]
        ])
        
        extraction_prompt = f"""Extract from this conversation:
1. crop_or_livestock: Specific crop/animal
2. region: Location in Kenya
3. issue: Problem description
4. additional_details: Symptoms/timeline

Conversation:
{conversation_text}

Respond ONLY with valid JSON:
{{
  "crop_or_livestock": "...",
  "region": "...",
  "issue": "...",
  "additional_details": "..."
}}

Use null for missing information."""

        response = llm.call([{"role": "user", "content": extraction_prompt}])
        
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        # Fallback: basic extraction
        return {
            "crop_or_livestock": "general crop",
            "region": "Kenya",
            "issue": messages[-1]["content"] if messages else "farming concern",
            "additional_details": None
        }
            
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return {
            "crop_or_livestock": "general crop",
            "region": "Kenya",
            "issue": "farming concern",
            "additional_details": None
        }


async def run_diagnosis_background(session_id: str, extracted_info: Dict[str, Any]):
    """Run diagnosis with comprehensive error handling"""
    try:
        logger.info(f"[TEST] Starting diagnosis for session {session_id}")
        
        crew = get_crew()
        
        # Build query
        query_parts = []
        if extracted_info.get("issue"):
            query_parts.append(extracted_info["issue"])
        if extracted_info.get("crop_or_livestock"):
            query_parts.append(f"Crop/Livestock: {extracted_info['crop_or_livestock']}")
        if extracted_info.get("additional_details"):
            query_parts.append(extracted_info["additional_details"])
        
        query = ". ".join(query_parts) if query_parts else "General farming advice needed"
        region = extracted_info.get("region", "Kenya")
        
        # Create MCP session
        crew.mcp_client.create_session(
            session_id=session_id,
            query=query,
            region=region
        )
        
        # Run crew with timeout protection
        inputs = {
            'query': query,
            'region': region,
            'session_id': session_id
        }
        
        logger.info(f"[START] Running crew for session {session_id}")
        result = crew.crew().kickoff(inputs=inputs)
        
        # Extract diagnosis
        if hasattr(result, 'raw'):
            diagnosis = result.raw
        elif hasattr(result, 'result'):
            diagnosis = result.result
        else:
            diagnosis = str(result)
        
        # Get context
        context = crew.mcp_client.get_context(session_id)
        
        # Update session
        session_data = get_session(session_id)
        if session_data:
            session_data["diagnosis"] = diagnosis
            session_data["status"] = "completed"
            
            if context:
                session_data["classification"] = {
                    "asset_type": context.asset_type.value,
                    "asset_name": context.asset_name or "Unknown",
                    "intent": context.intent.value
                }
                session_data["alert_triggered"] = context.alert_triggered
                if context.alert_severity:
                    session_data["alert_severity"] = context.alert_severity.value
            
            save_session(session_id, session_data)

        logger.info(f"[OK] Diagnosis completed for session {session_id}")

    except Exception as e:
        logger.error(f"[ERROR] Diagnosis error for session {session_id}: {e}", exc_info=True)

        # Update session with error
        session_data = get_session(session_id)
        if session_data:
            session_data["status"] = "failed"
            session_data["error"] = "We encountered an issue processing your request. Please try again or contact support."
            session_data["diagnosis"] = """I apologize, but I encountered an issue while analyzing your farm situation. 

Please try:
1. Providing more specific details about your problem
2. Starting a new conversation
3. Contacting our support team if the issue persists

We're here to help!"""
            save_session(session_id, session_data)


# API Endpoints

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "healthy",
        "service": "AgroSense Conversational API",
        "features": ["memory", "security", "fallback"],
        "providers": ["Gemini", "Groq", "Cohere"]
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    crew_status = "healthy" if crew_instance else "not_initialized"
    llm_status = "healthy" if conversational_llm else "not_initialized"
    redis_status = "connected" if USE_REDIS else "unavailable"
    
    #  Get provider status from model router
    provider_status = model_router.get_provider_status()
    
    return {
        "status": "healthy",
        "components": {
            "crew": crew_status,
            "llm": llm_status,
            "redis": redis_status,
            "providers": provider_status
        },
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """Main chat endpoint with rate limiting and memory"""
    
    # Rate limiting
    client_ip = get_client_ip(req)
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per minute."
        )
    
    try:
        logger.info(f"[CHAT] Chat from {client_ip}: {request.message[:100]}...")
        
        # Get or create session
        session_id = request.session_id or generate_session_id()
        session_data = get_session(session_id)
        
        if not session_data:
            session_data = {
                "session_id": session_id,
                "farmer_id": request.farmer_id,
                "created_at": datetime.now().isoformat(),
                "messages": [],
                "status": "chatting",
                "client_ip": client_ip
            }
        
        #  Get or create memory for this session
        memory = memory_manager.get_or_create(session_id)
        
        # Check message limit
        if len(session_data.get("messages", [])) >= MAX_SESSION_MESSAGES:
            return ChatResponse(
                message="You've reached the maximum number of messages for this session. Please start a new conversation.",
                session_id=session_id,
                requires_action=False
            )
        
        #  Add user message to memory
        memory.add_user_message(request.message)
        
        # Add user message to session
        session_data["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Check if diagnosis is ready
        if session_data.get("status") == "completed" and session_data.get("diagnosis"):
            diagnosis = session_data["diagnosis"]
            logger.info(f"✅ Returning completed diagnosis for session {session_id}")
            
            # Add AI response to memory
            memory.add_ai_message(diagnosis)
            
            response = ChatResponse(
                message=diagnosis,
                session_id=session_id,
                requires_action=False,
                classification=session_data.get("classification"),
                alert_triggered=session_data.get("alert_triggered", False),
                alert_severity=session_data.get("alert_severity")
            )
            
            session_data["last_diagnosis"] = diagnosis
            session_data["diagnosis"] = None
            session_data["status"] = "chatting"
            save_session(session_id, session_data)
            
            return response
        
        # If processing
        if session_data.get("status") == "processing":
            save_session(session_id, session_data)
            return ChatResponse(
                message="⏳ Your comprehensive diagnosis is still being prepared. Please check back in a moment.",
                session_id=session_id,
                requires_action=False
            )
        
        # Generate AI response with memory
        ai_response = await generate_conversational_response(
            request.message,
            session_data
        )
        
        #  Add AI response to memory
        memory.add_ai_message(ai_response["message"])
        
        # Add AI message to session
        session_data["messages"].append({
            "role": "assistant",
            "content": ai_response["message"],
            "timestamp": datetime.now().isoformat()
        })
        
        # Check if ready for diagnosis
        if ai_response["is_ready_for_diagnosis"]:
            extracted_info = await extract_information(session_data["messages"])
            logger.info(f"[INFO] Extracted: {extracted_info}")
            
            session_data["extracted_info"] = extracted_info
            session_data["status"] = "processing"
            save_session(session_id, session_data)
            
            # Queue diagnosis
            background_tasks.add_task(
                run_diagnosis_background,
                session_id,
                extracted_info
            )
            
            return ChatResponse(
                message=ai_response["message"],
                session_id=session_id,
                requires_action=True,
                action_type="diagnosis_started"
            )
        
        # Save and continue
        save_session(session_id, session_data)
        
        return ChatResponse(
            message=ai_response["message"],
            session_id=session_id,
            requires_action=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Chat error: {e}", exc_info=True)
        return ChatResponse(
            message="I apologize, but I encountered an unexpected error. Please try again or start a new conversation.",
            session_id=session_id if 'session_id' in locals() else generate_session_id(),
            requires_action=False
        )


@app.get("/api/v1/status/{session_id}")
async def check_status(session_id: str):
    """Check diagnosis status"""
    try:
        session_data = get_session(session_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        status = session_data.get("status", "unknown")
        
        response = {
            "session_id": session_id,
            "status": status,
            "message": f"Status: {status}"
        }
        
        if status == "completed":
            diagnosis = session_data.get("diagnosis")
            if diagnosis:
                response["diagnosis"] = diagnosis
                response["classification"] = session_data.get("classification")
                response["alert_triggered"] = session_data.get("alert_triggered", False)
                response["alert_severity"] = session_data.get("alert_severity")
                response["message"] = "Diagnosis ready!"
            else:
                response["status"] = "processing"
                response["message"] = "Still processing..."
        elif status == "failed":
            response["message"] = "Analysis failed"
            response["error"] = session_data.get("error", "Unknown error")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail="Error checking status")


@app.delete("/api/v1/session/{session_id}")
async def end_session(session_id: str):
    """End and delete session"""
    try:
        delete_session(session_id)
        #  Also delete memory
        memory_manager.delete(session_id)
        return {"message": "Session ended", "session_id": session_id}
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        raise HTTPException(status_code=500, detail="Error ending session")


@app.get("/api/v1/weather", response_model=WeatherResponse)
async def get_weather(region: str):
    """Get weather with fallback"""
    try:
        crew = get_crew()
        session_id = generate_session_id()
        
        crew.mcp_client.create_session(
            session_id=session_id,
            query="weather check",
            region=region
        )
        
        crew.weather_price_tool._run(
            session_id=session_id,
            region=region,
            asset_name="general"
        )
        
        context = crew.mcp_client.get_context(session_id)
        
        if context and context.regional_data:
            regional_data = context.regional_data
            weather = regional_data.get('weather', {})
            market = regional_data.get('market_prices', {})
            
            temp = weather.get('current_temp', 25.0)
            humidity = weather.get('humidity', 70.0)
            condition = weather.get('condition', 'Clear')
            
            commodity = market.get('commodity', 'General')
            price = market.get('current_price', 0)
            currency = market.get('currency', 'KES')
            
            price_str = f"{commodity}: {currency} {price:,.0f}" if price > 0 else "Price unavailable"
            
            crew.mcp_client.clear_session(session_id)
            
            return WeatherResponse(
                temperature=float(temp),
                humidity=float(humidity),
                condition=condition,
                market_price=price_str
            )
        
        # Fallback
        return WeatherResponse(
            temperature=25.0,
            humidity=70.0,
            condition="Data unavailable",
            market_price="Data unavailable"
        )
        
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return WeatherResponse(
            temperature=25.0,
            humidity=70.0,
            condition="Service unavailable",
            market_price="Service unavailable"
        )


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("[FARM] Starting AgroSense API v2.2.0...")
    logger.info(f"[INFO] Features: Memory, Security, Fallback Mechanisms")
    logger.info(f"[INFO] Storage: {'Redis' if USE_REDIS else 'In-Memory'}")
    logger.info(f"[INFO] AI Providers: Gemini, Groq, Cohere")

    try:
        get_crew()
        get_conversational_llm()
        logger.info("[INFO] AgroSense API ready!")
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )