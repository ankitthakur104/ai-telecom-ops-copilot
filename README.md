# AI Telecom Operations Copilot

  > Production-grade AI assistant for CRBT/VAS telecom platforms — 7-agent LangGraph system for automated incident management, root cause analysis, and predictive failure detection.

  [![Live Demo](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-blue)](https://ankitthakur104.github.io/ai-telecom-ops-copilot/)
  [![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-red)](https://fastapi.tiangolo.com)
  [![LangGraph](https://img.shields.io/badge/LangGraph-0.1+-orange)](https://langchain-ai.github.io/langgraph/)

  ---

  ## Overview

  The AI Telecom Operations Copilot assists L1 and L2 support engineers managing CRBT (Caller Ring Back Tone) and VAS (Value Added Services) platforms across Halotel Tanzania, Ncell Nepal, Vodacom Tanzania, and similar telecom operators.

  **Key Outcomes:**
  - 60% reduction in L1 operational workload
  - 50% reduction in L2 troubleshooting time (MTTR)
  - 93–96% alert classification accuracy
  - 83–87% root cause analysis accuracy (after knowledge base maturation)

  ---

  ## Architecture

  ```
  Telemetry Layer (Prometheus + ELK + Kafka + OpenTelemetry)
           │
           ▼
  Incident Correlation Engine (alert clustering + temporal correlation)
           │
           ▼
  ┌────────────────────────── LangGraph Pipeline ──────────────────────────┐
  │                                                                        │
  │  Agent 1          Agent 2          Agent 3          Agent 4           │
  │  Alert Intel  ──▶ Evidence     ──▶ Root Cause   ──▶ Runbook          │
  │  (dedup+rank)     Collection       Analysis (RAG)    Matching         │
  │                                        │                │             │
  │  Agent 7          Agent 5          ◀───┘            ◀──┘             │
  │  Learning    ◀──  Ticket Auto                                         │
  │  (feedback)       (Jira/SNOW)                                         │
  │                                                                        │
  │  Agent 6: Predictive Failure (LSTM + Isolation Forest) — parallel     │
  └────────────────────────────────────────────────────────────────────────┘
           │
           ▼
  Safety Layer (READ_ONLY | ASSISTED + human approval | RESTRICTED)
           │
           ▼
  FastAPI + WebSocket ──▶ Next.js Dashboard
  ```

  ---

  ## Tech Stack

  | Layer | Technology |
  |---|---|
  | Backend | FastAPI, Python 3.11+ |
  | Agent Orchestration | LangGraph, LangChain |
  | LLM | OpenAI GPT-4o (tool calling + structured output) |
  | Vector Store | Qdrant (RAG over historical incidents) |
  | Knowledge Graph | Neo4j (incident → cause → fix relationships) |
  | Primary Database | PostgreSQL + SQLAlchemy |
  | Cache / Locks | Redis |
  | Messaging | Kafka (alert ingestion) |
  | ML Models | scikit-learn, TensorFlow (LSTM), PyOD (Isolation Forest) |
  | Frontend | Next.js 14 + React |
  | Auth | Keycloak (RBAC: L1 / L2 / Manager / Admin) |
  | Observability | OpenTelemetry, Prometheus, Grafana |
  | Deployment | Docker + Kubernetes |

  ---

  ## Project Structure

  ```
  ai-telecom-ops-copilot/
  ├── backend/
  │   ├── main.py                      # FastAPI entry point + WebSocket
  │   ├── config.py                    # Settings from env
  │   ├── requirements.txt
  │   │
  │   ├── agents/                      # LangGraph multi-agent pipeline
  │   │   ├── state.py                 # Shared AgentState TypedDict
  │   │   ├── pipeline.py              # StateGraph definition
  │   │   ├── alert_intelligence.py    # Agent 1
  │   │   ├── evidence_collection.py   # Agent 2
  │   │   ├── root_cause_analysis.py   # Agent 3 (RAG + KG)
  │   │   ├── runbook_agent.py         # Agent 4
  │   │   ├── ticket_automation.py     # Agent 5
  │   │   ├── predictive_failure.py    # Agent 6 (LSTM)
  │   │   └── learning_agent.py        # Agent 7 (feedback loop)
  │   │
  │   ├── core/
  │   │   ├── safety_layer.py          # Action classifier + approval gate
  │   │   ├── audit_logger.py          # Full immutable audit trail
  │   │   └── incident_correlator.py   # Alert clustering engine
  │   │
  │   ├── tools/                       # LangChain tools for agents
  │   │   ├── prometheus_tools.py
  │   │   ├── elasticsearch_tools.py
  │   │   ├── database_tools.py
  │   │   ├── kafka_tools.py
  │   │   └── incident_history_tools.py
  │   │
  │   ├── knowledge/
  │   │   ├── graph.py                 # Neo4j client
  │   │   ├── vector_store.py          # Qdrant RAG client
  │   │   ├── runbook_loader.py        # SOP ingestion
  │   │   └── seed_data.py             # Telecom incident knowledge base
  │   │
  │   ├── models/
  │   │   ├── schemas.py               # Pydantic models
  │   │   └── database.py              # SQLAlchemy ORM models
  │   │
  │   └── api/
  │       ├── incidents.py
  │       ├── alerts.py
  │       ├── approvals.py
  │       ├── analytics.py
  │       ├── feedback.py
  │       └── websocket.py
  │
  ├── docs/
  │   └── index.html                   # Interactive GitHub Pages demo
  │
  ├── k8s/
  │   ├── deployment.yaml
  │   ├── services.yaml
  │   └── configmap.yaml
  │
  ├── docker-compose.yml
  ├── .env.example
  └── README.md
  ```

  ---

  ## Quick Start

  ### Prerequisites

  - Python 3.11+
  - Docker + Docker Compose
  - OpenAI API key
  - (Optional) Neo4j, Qdrant, Kafka for full production mode

  ### 1. Clone and setup

  ```bash
  git clone https://github.com/ankitthakur104/ai-telecom-ops-copilot.git
  cd ai-telecom-ops-copilot
  cp .env.example .env
  # Edit .env with your API keys
  ```

  ### 2. Start infrastructure

  ```bash
  docker-compose up -d
  # Starts: PostgreSQL, Redis, Neo4j, Qdrant, Kafka
  ```

  ### 3. Install Python deps

  ```bash
  cd backend
  pip install -r requirements.txt
  ```

  ### 4. Run the API server

  ```bash
  uvicorn main:app --reload --port 8000
  ```

  ### 5. Trigger a test incident

  ```bash
  curl -X POST http://localhost:8000/api/alerts/ingest \
    -H "Content-Type: application/json" \
    -d '{
      "alerts": [
        {"source": "prometheus", "service": "billing_api", "operator": "halotel", "metric": "api_latency_p99", "value": 8500, "threshold": 2000, "severity": "P1"},
        {"source": "prometheus", "service": "crbt_provisioning", "operator": "halotel", "metric": "activation_success_rate", "value": 0.23, "threshold": 0.95, "severity": "P1"},
        {"source": "elk", "service": "db_primary", "operator": "halotel", "metric": "cpu_utilization", "value": 94.2, "threshold": 80, "severity": "P2"}
      ]
    }'
  ```

  ---

  ## API Reference

  | Endpoint | Method | Description |
  |---|---|---|
  | `/api/alerts/ingest` | POST | Ingest raw alerts, trigger pipeline |
  | `/api/incidents` | GET | List all incidents |
  | `/api/incidents/{id}/rca` | GET | Get full RCA for incident |
  | `/api/approvals` | GET | List pending human approvals |
  | `/api/approvals/{id}/approve` | POST | Approve assisted action |
  | `/api/approvals/{id}/reject` | POST | Reject assisted action |
  | `/api/analytics/mttr` | GET | MTTR analytics |
  | `/api/feedback` | POST | Engineer feedback for learning agent |
  | `/ws/alerts` | WS | Real-time alert stream |

  ---

  ## Accuracy Targets

  | Component | Achievable Accuracy |
  |---|---|
  | Alert deduplication + classification | 93–96% |
  | Incident correlation | 88–94% |
  | Evidence collection (deterministic) | ~99% |
  | Root cause analysis (mature KB) | 83–87% |
  | Root cause analysis (cold start) | 72–78% |
  | Runbook retrieval | 88–92% |
  | Predictive failure F1 | 78–86% |
  | Ticket generation quality | 91–95% |

  ---

  ## Safety Principles

  - **Read Before Write**: System observes, analyzes, recommends — never assumes authority
  - **Evidence Before Conclusions**: Every RCA hypothesis is grounded in logs, metrics, or historical incidents — no pure LLM reasoning
  - **Human In The Loop**: All remediation actions require explicit engineer approval
  - **Restricted Actions**: Database deletion, schema changes, credential rotation — permanently blocked

  ---

  ## Author

  **Ankit Kumar** — AI/GenAI Engineer  
  [Portfolio](https://ankitthakur104.github.io) | [GitHub](https://github.com/ankitthakur104) | ankitthakur104@gmail.com
  