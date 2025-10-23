# Resync System Architecture

## High-Level Architecture

```
+----------------------+
|      User (Operator) |
+----------+----------+
           |
           v
+----------+----------+     +------------------+
|   Chatbot (Frontend) |<----> +     AI Agent System |
|  (Web Interface)     |      |
+----------+----------+     +--------+--------+
           |                 |               |
           v                 |               |
+----------+----------+     +--------+--------+
|   Dashboard (UI)     |     |  Knowledge Graph |
|  (Status Visualization)|    |  (RAG System)    |
+----------------------+     +------------------+
                                      |
                                      v
                               +--------+--------+
                               |   TWS API         |
                               |  (HCL Automation) |
                               +--------+--------+
                                      |
                                      v
                              +--------+--------+
                              |  External Services |
                              |  (Validation, Audit)|
                              +-------------------+

```

## Component Details

### 1. User Interface Layer
- **Chatbot Interface**: Primary interaction point for operators
- **Dashboard**: Real-time visualization of system status
- **Revisao Humana**: Manual review interface for knowledge graph

### 2. AI Agent System
- **Agent Manager**: Controls lifecycle of specialized agents
- **Resync Agents**: Handle specific tasks like:
  - Job status queries
  - Failure analysis
  - Knowledge retrieval
- **IA Auditor**: Monitors and validates knowledge graph entries

### 3. Knowledge Graph
- **RAG (Retrieval-Augmented Generation)**:
  - Base de conhecimento inicial (Excel → Qdrant)
  - Continuous learning system
  - Semantic search capabilities

### 4. TWS Integration Layer
- **TWS API Client**:
  - Real-time job status monitoring
  - Execution control
- **Mock TWS**: Simulation environment for development

### 5. External Services
- **Validation Services**:
  - Syntax validation
  - Security checks
- **Audit System**:
  - Tracks all operations
  - Generates compliance reports

## Data Flow Diagram

```
User → Chatbot → Agent System → [TWS API + Knowledge Graph]
                        ↖_________ Audit System
```

## Deployment Architecture

```
[Client Browser]
    ↓ HTTPS
[Reverse Proxy (NGINX)]
    ↓
[Load Balancer]
    ↓
[FastAPI Workers (Resync)]
    ↓
[Redis Cache] → [TWS API]
    ↓               ↓
[Knowledge Graph] [PostgreSQL]
```

## Technology Stack

| Layer           | Technologies Used                                    |
|----------------|-----------------------------------------------------|
| Frontend       | HTML, CSS, JavaScript (React planned)             |
| API            | FastAPI, Pydantic, Python 3.13+                  |
| AI Components  | Llama3, Gemini, Qdrant, Litellm                   |
| Data Storage   | PostgreSQL, Redis, Qdrant Vector DB              |
| Infrastructure | Docker (optional), Uvicorn, Gunicorn              |
| Monitoring     | Prometheus, OpenTelemetry                         |
| Security       | OAuth2, JWT, SSL/TLS                              |
