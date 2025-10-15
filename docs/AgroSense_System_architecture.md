# 🌾 AgroSense System Architecture

## Overview

The **AgroSense Multi-Asset Advisory System** is an intelligent agriculture assistant that integrates **multi-agent reasoning**, **Retrieval-Augmented Generation (RAG)**, and **workflow automation** to provide farmers with timely and localized insights.

It helps diagnose **crop and livestock health issues**, provides **context-aware recommendations** using regional agricultural data, and can trigger **automated alerts** (SMS, email, or logs) for critical events such as disease detection.

---

### ⚙️ Core Workflow Summary

1. **Farmer Query (Frontend)**  
   Farmers submit questions (e.g., “My cow has a fever in Nakuru”) through the Streamlit web interface.

2. **FastAPI Backend**  
   The backend receives and validates the query, then sends it to the **Supervisor Agent** which coordinates agent collaboration.

3. **Multi-Agent System (MCP-Coordinated)**  
   - **Orchestrator Agent** classifies the query (Crop, Livestock, Finance).  
   - **Agri-Knowledge Agent** retrieves relevant context from the **Vector Database** (documents tagged by `asset_type` and `region`).  
   - **Crop Diagnostic Agent** or **Livestock Vet Agent** reasons on the retrieved data to form a diagnosis.  
   - **Weather/Price Agent** adds contextual information (rainfall, commodity prices).  
   - **Action Agent** prepares an actionable payload for automation.

4. **Data & Intelligence Layer**  
   Agricultural documents are uploaded via `/upload-doc`, tagged with metadata, and stored in **Chroma/Pinecone** for efficient vector retrieval.

5. **Automation (n8n Workflow)**  
   When the Action Agent identifies a critical condition, it sends a payload to `/trigger-action`, which invokes an **n8n workflow**:
   - Sends SMS alerts via Twilio/WhatsApp  
   - Logs the event in Google Sheets or a database  
   - Notifies local veterinarians or extension officers by email

6. **Response Delivery**  
   The Supervisor compiles and formats the agents’ reasoning into a clear, actionable response displayed back to the farmer on the frontend.

---

## 🧠 System Flowchart

```mermaid
flowchart TD
    %% ========= FRONTEND =========
    subgraph UI["🌾 Streamlit Frontend (Farmer Interface)"]
        UIQ["Farmer Query Input\n(e.g. 'My cow has a fever in Nakuru')"]
        UIQ -->|POST /ask| API
    end

    %% ========= BACKEND CORE =========
    subgraph Backend["🚀 FastAPI Backend"]
        API["/ask Endpoint\nReceives query → validates → sends to Orchestrator"]
        MCP["MCP Client\n(Session & Shared Context)\n(session_id, asset_type, region)"]
        Supervisor["Supervisor / Crew Manager\nCoordinates Agent Collaboration"]
        ActionAPI["/trigger-action Endpoint\nReceives ActionAgent payload → calls n8n"]
    end

    %% ========= MULTI-AGENT CORE =========
    subgraph MultiAgent["🧠 AgroSense Multi-Agent System"]
        Orchestrator["Orchestrator Agent (Manager)\n- Classifies intent (Crop/Livestock/Finance)\n- Sets MCP context\n- Routes query"]
        AgriKnowledge["Agri-Knowledge Agent (RAG Specialist)\n- Retrieves from Vector DB\n- Synthesizes background info"]
        CropAgent["Crop Diagnostic Agent\n- Diagnoses plant diseases, pests, deficiencies"]
        LivestockAgent["Livestock Vet Agent\n- Diagnoses animal health issues"]
        WeatherPrice["Weather/Price Agent\n- Fetches real-time weather & market data"]
        ActionAgent["Action Agent\n- Prepares actionable alerts\n- Calls /trigger-action"]
    end

    %% ========= DATA SYSTEMS =========
    subgraph DataLayer["📚 Data & Intelligence Layer"]
        VectorDB["Vector Database (Chroma / Pinecone)\nChunked Agricultural PDFs\nMetadata: asset_type, region"]
        DocsUpload["/upload-doc Endpoint\nRequires asset_type + region metadata"]
    end

    %% ========= AUTOMATION =========
    subgraph Automation["⚙️ n8n Workflow Automation"]
        N8N["n8n Webhook Trigger\n(Receives FastAPI payload)"]
        Branch["IF Node: Check action_type"]
        SMS["Twilio/WhatsApp Node\nSend critical alert SMS"]
        Sheet["Google Sheets / DB Node\nLog alert"]
        Email["Email Node\nNotify vet/extension officer"]
    end

    %% ========= FLOW CONNECTIONS =========
    %% Frontend to Backend
    API --> Supervisor
    Supervisor --> Orchestrator
    Orchestrator --> MCP
    Orchestrator --> AgriKnowledge
    Orchestrator -->|Crop| CropAgent
    Orchestrator -->|Livestock| LivestockAgent
    Orchestrator -->|Finance| WeatherPrice

    %% RAG retrieval
    AgriKnowledge -->|"Query by asset_type & region"| VectorDB
    VectorDB --> AgriKnowledge
    DocsUpload --> VectorDB

    %% Reasoning flow
    AgriKnowledge --> CropAgent
    AgriKnowledge --> LivestockAgent
    WeatherPrice --> LivestockAgent
    WeatherPrice --> CropAgent

    %% Diagnostic to Action
    CropAgent --> ActionAgent
    LivestockAgent --> ActionAgent
    ActionAgent --> ActionAPI
    ActionAPI --> N8N
    N8N --> Branch
    Branch -->|EMERGENCY_VET_ALERT| SMS
    Branch -->|EMERGENCY_VET_ALERT| Sheet
    Branch -->|EMERGENCY_VET_ALERT| Email

    %% Response back to user
    Supervisor -->|"Final formatted response"| UIQ

    %% ========= STYLE =========
    classDef agents fill:#e6f7ff,stroke:#0094c6,stroke-width:1px,color:#003049;
    classDef backend fill:#fff8e1,stroke:#e0a800,stroke-width:1px,color:#4b3832;
    classDef data fill:#e7ffe7,stroke:#5a995a,stroke-width:1px,color:#003300;
    classDef automation fill:#ffe5e5,stroke:#d64545,stroke-width:1px,color:#330000;
    classDef ui fill:#f0f9ff,stroke:#3399cc,stroke-width:1px,color:#003344;

    class UI,UIQ ui;
    class Backend,API,MCP,Supervisor,ActionAPI backend;
    class MultiAgent,Orchestrator,AgriKnowledge,CropAgent,LivestockAgent,WeatherPrice,ActionAgent agents;
    class DataLayer,VectorDB,DocsUpload data;
    class Automation,N8N,Branch,SMS,Sheet,Email automation;
