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
import asyncio
from functools import lru_cache
import threading

# Memory optimizations for deployment
os.environ["TOKENIZERS_PARALLELISM"] = "false"
gc.set_threshold(700, 10, 10)

# IMPORTANT: Don't import CrewAI at module level - import only when needed
# from src.agrosense.crew import AgroSenseCrew  # ❌ DON'T DO THIS

import sys
import codecs

if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, errors='replace')
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, errors='replace')

# Setup logging
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)

# Initialize Redis
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
    logger.info("[OK] Connected to Redis")
    USE_REDIS = True
except:
    logger.warning("[WARN] Redis unavailable. Using in-memory storage")
    USE_REDIS = False

# In-memory fallback
sessions: Dict[str, Dict[str, Any]] = {}
rate_limit_storage: Dict[str, List[datetime]] = defaultdict(list)

# ============================================================================
# LAZY LOADING IMPLEMENTATION
# ============================================================================

# Global instances - initialized as None
crew_instance = None
conversational_llm = None
crew_lock = threading.Lock()  # Thread-safe initialization
llm_lock = threading.Lock()

# Track initialization state
CREW_INITIALIZING = False
LLM_INITIALIZING = False

# Constants
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60
MAX_MESSAGE_LENGTH = 2000
MAX_SESSION_MESSAGES = 100
SESSION_TTL = 3600


def lazy_import_crew():
    """
    Lazy import CrewAI modules only when needed.
    This prevents loading heavy dependencies at startup.
    """
    try:
        from src.agrosense.crew import AgroSenseCrew
        from src.agrosense.core.model_router import get_model_for_task, TaskType, model_router
        from src.agrosense.core.prompts import PromptLibrary
        from src.agrosense.core.langchain_memory import memory_manager
        
        return {
            'AgroSenseCrew': AgroSenseCrew,
            'get_model_for_task': get_model_for_task,
            'TaskType': TaskType,
            'model_router': model_router,
            'PromptLibrary': PromptLibrary,
            'memory_manager': memory_manager
        }
    except Exception as e:
        logger.error(f"Failed to import CrewAI modules: {e}")
        raise


@lru_cache(maxsize=1)
def get_crew_modules():
    """
    Cached lazy import - imports only once and caches the result.
    Using lru_cache ensures thread-safe singleton behavior.
    """
    return lazy_import_crew()


def get_crew(timeout: int = 30):
    """
    Get or create crew instance with lazy loading and timeout protection.
    
    Args:
        timeout: Maximum seconds to wait for initialization
    """
    global crew_instance, CREW_INITIALIZING
    
    # Fast path: already initialized
    if crew_instance is not None:
        return crew_instance
    
    # Acquire lock for initialization
    with crew_lock:
        # Double-check after acquiring lock
        if crew_instance is not None:
            return crew_instance
        
        # Check if another thread is initializing
        if CREW_INITIALIZING:
            logger.info("Crew initialization in progress, waiting...")
            # Wait for initialization to complete
            start_time = datetime.now()
            while CREW_INITIALIZING and (datetime.now() - start_time).seconds < timeout:
                import time
                time.sleep(0.5)
            
            if crew_instance is not None:
                return crew_instance
            else:
                raise HTTPException(
                    status_code=503,
                    detail="Crew initialization timeout. Please retry."
                )
        
        # Initialize crew
        CREW_INITIALIZING = True
        try:
            logger.info("[LAZY] Loading CrewAI modules...")
            modules = get_crew_modules()
            AgroSenseCrew = modules['AgroSenseCrew']
            
            logger.info("[LAZY] Initializing AgroSense Crew...")
            crew_instance = AgroSenseCrew()
            logger.info("[OK] Crew initialized successfully")
            
            return crew_instance
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize crew: {e}", exc_info=True)
            crew_instance = None  # Reset on failure
            raise HTTPException(
                status_code=503,
                detail=f"Service initialization failed: {str(e)[:100]}"
            )
        finally:
            CREW_INITIALIZING = False


def get_conversational_llm(timeout: int = 30):
    """
    Get LLM with lazy loading and automatic fallback.
    
    Args:
        timeout: Maximum seconds to wait for initialization
    """
    global conversational_llm, LLM_INITIALIZING
    
    # Fast path: already initialized
    if conversational_llm is not None:
        return conversational_llm
    
    with llm_lock:
        # Double-check after acquiring lock
        if conversational_llm is not None:
            return conversational_llm
        
        # Check if initializing
        if LLM_INITIALIZING:
            logger.info("LLM initialization in progress, waiting...")
            start_time = datetime.now()
            while LLM_INITIALIZING and (datetime.now() - start_time).seconds < timeout:
                import time
                time.sleep(0.5)
            
            if conversational_llm is not None:
                return conversational_llm
            else:
                raise HTTPException(
                    status_code=503,
                    detail="LLM initialization timeout. Please retry."
                )
        
        # Initialize LLM
        LLM_INITIALIZING = True
        try:
            logger.info("[LAZY] Loading LLM with model router...")
            modules = get_crew_modules()
            get_model_for_task = modules['get_model_for_task']
            TaskType = modules['TaskType']
            
            conversational_llm = get_model_for_task(
                task_type=TaskType.CONVERSATION,
                temperature=0.7
            )
            logger.info("[OK] Conversational LLM initialized")
            
            return conversational_llm
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}", exc_info=True)
            conversational_llm = None  # Reset on failure
            raise HTTPException(
                status_code=503,
                detail="AI service temporarily unavailable"
            )
        finally:
            LLM_INITIALIZING = False


def get_memory_manager():
    """Lazy load memory manager"""
    modules = get_crew_modules()
    return modules['memory_manager']


def get_prompt_library():
    """Lazy load prompt library"""
    modules = get_crew_modules()
    return modules['PromptLibrary']


# ============================================================================
# HEALTH CHECK WITH LAZY STATUS
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check that doesn't trigger initialization.
    Shows component status without loading them.
    """
    crew_status = "initialized" if crew_instance else "not_loaded"
    llm_status = "initialized" if conversational_llm else "not_loaded"
    redis_status = "connected" if USE_REDIS else "unavailable"
    
    # Get provider status only if model router is loaded
    provider_status = {}
    try:
        if crew_instance or conversational_llm:
            modules = get_crew_modules()
            model_router = modules['model_router']
            provider_status = model_router.get_provider_status()
    except:
        provider_status = {"status": "not_loaded"}
    
    return {
        "status": "healthy",
        "components": {
            "crew": crew_status,
            "llm": llm_status,
            "redis": redis_status,
            "providers": provider_status
        },
        "initialization": {
            "crew_initializing": CREW_INITIALIZING,
            "llm_initializing": LLM_INITIALIZING
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint - no heavy initialization"""
    return {
        "status": "healthy",
        "service": "AgroSense Conversational API",
        "version": "2.2.0",
        "features": ["lazy_loading", "memory", "security", "fallback"],
        "providers": ["Gemini", "Groq", "Cohere"],
        "note": "Heavy components load on first use"
    }


# ============================================================================
# WARMUP ENDPOINT (OPTIONAL)
# ============================================================================

@app.post("/api/v1/warmup")
async def warmup(background_tasks: BackgroundTasks):
    """
    Optional endpoint to pre-initialize heavy components.
    Can be called by deployment scripts or health checks.
    """
    def warmup_task():
        try:
            logger.info("[WARMUP] Starting component initialization...")
            get_crew()
            get_conversational_llm()
            logger.info("[WARMUP] All components ready!")
        except Exception as e:
            logger.error(f"[WARMUP] Failed: {e}")
    
    if crew_instance is None or conversational_llm is None:
        background_tasks.add_task(warmup_task)
        return {
            "message": "Warmup initiated in background",
            "status": "initializing"
        }
    else:
        return {
            "message": "All components already initialized",
            "status": "ready"
        }


# ============================================================================
# SECURITY & UTILITY FUNCTIONS (unchanged)
# ============================================================================

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
    
    rate_limit_storage[client_ip] = [
        req_time for req_time in rate_limit_storage[client_ip]
        if req_time > cutoff
    ]
    
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    rate_limit_storage[client_ip].append(now)
    return True


def sanitize_input(text: str) -> str:
    """Sanitize user input"""
    dangerous_patterns = ["<script", "javascript:", "onerror=", "onclick="]
    sanitized = text
    for pattern in dangerous_patterns:
        sanitized = sanitized.replace(pattern, "")
    return sanitized.strip()


def generate_session_id() -> str:
    """Generate secure session ID"""
    return secrets.token_urlsafe(32)


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


# ============================================================================
# REQUEST/RESPONSE MODELS (unchanged)
# ============================================================================

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


# ============================================================================
# API ENDPOINTS (updated to use lazy loading)
# ============================================================================

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


async def generate_conversational_response(
    message: str, 
    session_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate response with conversation memory using Prompt Library"""
    
    try:
        # Lazy load LLM and modules
        llm = get_conversational_llm()
        PromptLibrary = get_prompt_library()
        
        messages = PromptLibrary.format_prompt(
            "conversation",
            message=message
        )
        
        if session_data and "messages" in session_data:
            history = []
            for msg in session_data["messages"][-10:]:
                history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            messages = [messages[0]] + history + [messages[-1]]
        
        response = llm.call(messages)
        ai_message = response if isinstance(response, str) else str(response)
        
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
        
        # Lazy load crew
        crew = get_crew()
        
        query_parts = []
        if extracted_info.get("issue"):
            query_parts.append(extracted_info["issue"])
        if extracted_info.get("crop_or_livestock"):
            query_parts.append(f"Crop/Livestock: {extracted_info['crop_or_livestock']}")
        if extracted_info.get("additional_details"):
            query_parts.append(extracted_info["additional_details"])
        
        query = ". ".join(query_parts) if query_parts else "General farming advice needed"
        region = extracted_info.get("region", "Kenya")
        
        crew.mcp_client.create_session(
            session_id=session_id,
            query=query,
            region=region
        )
        
        inputs = {
            'query': query,
            'region': region,
            'session_id': session_id
        }
        
        logger.info(f"[START] Running crew for session {session_id}")
        result = crew.crew().kickoff(inputs=inputs)
        
        if hasattr(result, 'raw'):
            diagnosis = result.raw
        elif hasattr(result, 'result'):
            diagnosis = result.result
        else:
            diagnosis = str(result)
        
        context = crew.mcp_client.get_context(session_id)
        
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


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    req: Request
):
    """Main chat endpoint with rate limiting and memory"""
    
    client_ip = get_client_ip(req)
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per minute."
        )
    
    try:
        logger.info(f"[CHAT] Chat from {client_ip}: {request.message[:100]}...")
        
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
        
        # Lazy load memory manager
        memory_manager = get_memory_manager()
        memory = memory_manager.get_or_create(session_id)
        
        if len(session_data.get("messages", [])) >= MAX_SESSION_MESSAGES:
            return ChatResponse(
                message="You've reached the maximum number of messages for this session. Please start a new conversation.",
                session_id=session_id,
                requires_action=False
            )
        
        memory.add_user_message(request.message)
        
        session_data["messages"].append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        })
        
        if session_data.get("status") == "completed" and session_data.get("diagnosis"):
            diagnosis = session_data["diagnosis"]
            logger.info(f"✅ Returning completed diagnosis for session {session_id}")
            
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
        
        if session_data.get("status") == "processing":
            save_session(session_id, session_data)
            return ChatResponse(
                message="⏳ Your comprehensive diagnosis is still being prepared. Please check back in a moment.",
                session_id=session_id,
                requires_action=False
            )
        
        ai_response = await generate_conversational_response(
            request.message,
            session_data
        )
        
        memory.add_ai_message(ai_response["message"])
        
        session_data["messages"].append({
            "role": "assistant",
            "content": ai_response["message"],
            "timestamp": datetime.now().isoformat()
        })
        
        if ai_response["is_ready_for_diagnosis"]:
            extracted_info = await extract_information(session_data["messages"])
            logger.info(f"[INFO] Extracted: {extracted_info}")
            
            session_data["extracted_info"] = extracted_info
            session_data["status"] = "processing"
            save_session(session_id, session_data)
            
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
        # Lazy load memory manager only if needed
        try:
            memory_manager = get_memory_manager()
            memory_manager.delete(session_id)
        except:
            pass  # Memory manager not loaded yet
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
    """
    Lightweight startup - NO heavy initialization!
    Components load on first use.
    """
    logger.info("[FARM] Starting AgroSense API v2.2.0...")
    logger.info(f"[INFO] Features: Lazy Loading, Memory, Security, Fallback")
    logger.info(f"[INFO] Storage: {'Redis' if USE_REDIS else 'In-Memory'}")
    logger.info(f"[INFO] AI Providers: Gemini, Groq, Cohere")
    logger.info("[INFO] ✅ API ready! Heavy components will load on first request.")
    
    # Optional: Pre-warm in background (uncomment if needed)
    # import asyncio
    # asyncio.create_task(background_warmup())


async def background_warmup():
    """
    Optional background warmup task.
    Initializes components after startup completes.
    """
    try:
        import asyncio
        await asyncio.sleep(5)  # Wait 5 seconds after startup
        logger.info("[WARMUP] Background initialization starting...")
        get_crew()
        get_conversational_llm()
        logger.info("[WARMUP] ✅ All components pre-loaded!")
    except Exception as e:
        logger.warning(f"[WARMUP] Background init failed (non-critical): {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("[SHUTDOWN] Cleaning up resources...")
    
    global crew_instance, conversational_llm
    crew_instance = None
    conversational_llm = None
    
    # Clear cache
    get_crew_modules.cache_clear()
    
    logger.info("[SHUTDOWN] ✅ Cleanup complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        timeout_keep_alive=75,  # Longer timeout for crew operations
        limit_concurrency=100,
        limit_max_requests=10000
    )