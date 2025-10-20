# 🌾 AgroSense AI - Intelligent Agricultural Advisory System

**AgroSense** is an advanced AI-powered agricultural advisory system designed for Kenyan farmers. It combines multi-agent AI orchestration, RAG (Retrieval-Augmented Generation), real-time weather data, and market intelligence to provide comprehensive farming diagnoses and recommendations.

---

## 🎯 **Key Features**

### **AI & Intelligence**
- ✅ **Multi-Agent System** (CrewAI) - 5 specialized agents working collaboratively
- ✅ **RAG Pipeline** - Pinecone vector database with agricultural knowledge
- ✅ **LangChain Memory** - Context-aware conversations with history
- ✅ **Model Abstraction** - Intelligent routing between Gemini, GPT, Claude
- ✅ **Fallback Mechanisms** - Automatic failover when services are down
- ✅ **Prompt Engineering** - Advanced techniques (few-shot, chain-of-thought)

### **Backend & API**
- ✅ **FastAPI** - High-performance async REST API
- ✅ **Authentication** - JWT tokens + API key support
- ✅ **Rate Limiting** - Protection against abuse
- ✅ **Session Management** - Redis-based persistent memory
- ✅ **Error Handling** - Comprehensive fallback strategies

### **Data & Integration**
- ✅ **Weather API** - OpenWeatherMap integration
- ✅ **Market Prices** - Real-time commodity pricing
- ✅ **n8n Workflows** - Automated alerts and notifications
- ✅ **MCP (Model Context Protocol)** - Centralized state management

### **Deployment**
- ✅ **Docker** - Production-ready containerization
- ✅ **Docker Compose** - Full stack orchestration
- ✅ **Health Checks** - Service monitoring
- ✅ **Cloud Ready** - Deployable to AWS, GCP, Azure, Railway

---

## 🏗️ **System Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    AgroSense Architecture                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────────────────────────────┐
│   Streamlit  │─────▶│          FastAPI Backend             │
│   Frontend   │      │   ┌──────────────────────────────┐   │
└──────────────┘      │   │   Authentication Layer       │   │
                      │   │  (JWT + API Keys + Rate Limit)│   │
                      │   └──────────────────────────────┘   │
                      │   ┌──────────────────────────────┐   │
                      │   │   Model Router               │   │
                      │   │  (Gemini/GPT/Claude + Fallback)│ │
                      │   └──────────────────────────────┘   │
                      │   ┌──────────────────────────────┐   │
                      │   │   LangChain Memory           │   │
                      │   │  (Conversation Context)       │   │
                      │   └──────────────────────────────┘   │
                      └──────────────────────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │                               │
            ┌─────────▼────────┐           ┌─────────▼────────┐
            │   CrewAI Agents  │           │   MCP Client     │
            │  ┌─────────────┐ │           │ (State Manager)  │
            │  │Orchestrator │ │           └──────────────────┘
            │  │  Knowledge  │ │
            │  │   Weather   │ │           ┌─────────────────┐
            │  │ Diagnostic  │ │           │   Redis Cache   │
            │  │   Action    │ │           │  (Sessions)     │
            │  └─────────────┘ │           └─────────────────┘
            └──────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
┌───────▼──────┐ ┌───▼────────┐ ┌─▼──────────┐
│  RAG Tool    │ │  Weather   │ │  n8n Alert │
│  (Pinecone)  │ │  API Tool  │ │    Tool    │
└──────────────┘ └────────────┘ └────────────┘
```

---

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- API Keys:
  - Google Gemini API
  - Pinecone
  - OpenWeatherMap
  - (Optional) OpenAI, Anthropic, Cohere

### **Installation**

#### **Option 1: Local Development**

```bash
# Clone repository
git clone https://github.com/Ushindisidi/agrosense.git
cd agrosense

# Create virtual environment
python -m venv venv
source venv/scripts/activate  

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your API keys

# Run backend
uvicorn src.agrosense.main:app --reload --port 8000

# Run frontend (in another terminal)
streamlit run frontend/streamlit_app.py
```

#### **Option 2: Docker (Recommended)**

```bash
# Clone repository
git clone https://github.com/Ushindisidi/agrosense.git
cd agrosense

# Create .env file
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access services:
# API: http://localhost:8000
# Frontend: http://localhost:8501
# n8n: http://localhost:5678
# API Docs: http://localhost:8000/docs
```

---

## 🔐 **Authentication**

### **Register a New User**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "farmer1",
    "email": "farmer1@example.com",
    "password": "securepassword",
    "region": "Nairobi"
  }'
```

### **Login**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "farmer1",
    "password": "securepassword"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### **Using the Token**
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "My maize has brown spots on leaves"
  }'
```

### **Using API Key**
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "X-API-Key: agrosense_demo_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "My maize has brown spots on leaves"
  }'
```

---

## 📡 **API Endpoints**

### **Authentication**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login and get token |
| GET | `/api/v1/auth/me` | Get current user profile |

### **Chat & Diagnosis**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send message and get AI response |
| GET | `/api/v1/status/{session_id}` | Check diagnosis status |
| DELETE | `/api/v1/session/{session_id}` | End session |

### **Weather & Data**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/weather?region=Nairobi` | Get weather & market data |

### **Health & Monitoring**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API status |
| GET | `/health` | Detailed health check |
| GET | `/docs` | Interactive API documentation |

---

## 🧠 **Multi-Agent System**

### **Agents & Roles**

1. **Orchestrator Agent**
   - Routes queries to appropriate agents
   - Classifies crop/livestock and intent
   - Coordinates workflow

2. **Knowledge Agent**
   - Searches agricultural knowledge base (RAG)
   - Retrieves relevant research and best practices
   - Uses Pinecone vector database

3. **Weather & Market Agent**
   - Fetches real-time weather data
   - Retrieves market prices
   - Provides regional insights

4. **Diagnostic Agent**
   - Analyzes symptoms and data
   - Generates comprehensive diagnosis
   - Uses chain-of-thought reasoning

5. **Action Agent**
   - Evaluates alert severity
   - Triggers n8n workflows
   - Sends notifications

---

## 🔧 **Configuration**

### **Environment Variables**

Create a `.env` file:

```env
# AI Model APIs
GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
COHERE_API_KEY=your_cohere_key

# Vector Database
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=your_env
PINECONE_INDEX_NAME=agrosense

# Weather & Data
OPENWEATHER_API_KEY=your_weather_key

# n8n Integration
N8N_WEBHOOK_URL=http://n8n:5678/webhook/agrosense-alert

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Security
JWT_SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=http://localhost:8501,http://localhost:3000

# App Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## 📦 **Project Structure**

```
agrosense/
├── src/
│   └── agrosense/
│       ├── main.py                 # FastAPI application
│       ├── crew.py                 # CrewAI multi-agent setup
│       ├── auth/
│       │   └── security.py         # Authentication
│       ├── core/
│       │   ├── mcp_client.py       # State management
│       │   ├── schemas.py          # Data models
│       │   ├── model_router.py     # AI model abstraction
│       │   ├── prompts.py          # Prompt library
│       │   └── langchain_memory.py # Conversation memory
│       ├── tools/
│       │   ├── rag_tool.py         # Knowledge retrieval
│       │   ├── weather_price_tool.py
│       │   └── n8n_alert_tool.py
│       └── config/
│           ├── agents.yaml
│           └── tasks.yaml
├── frontend/
│   └── streamlit_app.py            # UI
├── knowledge/                       # PDF documents
├── tests/                           # Unit tests
├── docs/                            # Documentation
├── Dockerfile                       # API container
├── Dockerfile.frontend              # Frontend container
├── docker-compose.yml               # Full stack
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🧪 **Testing**

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_crew.py

# Test with coverage
pytest --cov=src/agrosense tests/

# Test API endpoints
pytest tests/test_api.py -v
```

---

## 🚢 **Deployment**

### **Railway**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Add environment variables
railway variables set GOOGLE_API_KEY=your_key

# Deploy
railway up
```

### **Docker Hub**
```bash
# Build and tag
docker build -t yourusername/agrosense:latest .

# Push
docker push yourusername/agrosense:latest

# Pull and run on server
docker pull yourusername/agrosense:latest
docker run -d -p 8000:8000 --env-file .env yourusername/agrosense:latest
```

### **AWS ECS / Azure / GCP**
Refer to `docs/deployment/` for platform-specific guides.

---

## 📊 **Monitoring & Logs**

```bash
# View API logs
docker-compose logs -f api

# View all services
docker-compose logs -f

# Check service health
curl http://localhost:8000/health

# Redis monitoring
docker exec -it agrosense-redis redis-cli
```

---

## 🤝 **Contributing**

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📝 **License**

MIT License - see [LICENSE](LICENSE) file

---

## 👥 **Team**

Built with ❤️ for Kenyan farmers

---

## 📞 **Support**

- 📧 Email: sidiushindi@gmail.com

---

## 🙏 **Acknowledgments**

- CrewAI for multi-agent orchestration
- LangChain for conversation memory
- Pinecone for vector database
- FastAPI for the amazing framework
- All contributors and supporters