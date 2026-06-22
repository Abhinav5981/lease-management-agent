# Lease Management Agent

An AI-powered lease management platform for Dubai real estate. A LangGraph ReAct agent handles the full tenancy lifecycle — searching units, drafting leases, initiating renewals, logging maintenance — while a RAG knowledge base answers RERA policy and tenant FAQ questions.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Engine 24+, Compose v2)
- [Modal API key](https://console.groq.com/)

---

## Setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd lease-management-agent
cp .env.example .env
```

Open `.env` and set your modal API key:

```
Modal_API_KEY=gsk_your_key_here
```

Everything else in `.env.example` works as-is for local Docker.

### 2. Start all services

```bash
docker-compose up -d
```

This starts four containers:

| Container | Port | Role |
|---|---|---|
| `lease_postgres` | 5432 | PostgreSQL — schema + seed data auto-loaded |
| `lease_qdrant` | 6333 | Qdrant vector store |
| `lease_backend` | 8000 | FastAPI + LangGraph agent |
| `lease_frontend` | 3000 | Next.js UI |

First start takes 2–3 minutes (fastembed model downloads ~130 MB on first agent call).

### 3. Seed the knowledge base

Run once after the backend is healthy:

```bash
docker exec lease_backend python scripts/seed_knowledge.py
```

This embeds 5 policy documents into Qdrant (RERA rules, tenant FAQ, move-in/out guides, renewal policies). The agent uses these to answer policy questions without hallucinating.

### 4. Verify everything is running

```bash
# All four containers should show "healthy" or "running"
docker-compose ps

# Backend health
curl http://localhost:8000/health

# Sample API call — should return 75 leases
curl "http://localhost:8000/api/v1/leases?limit=5"

# Open the UI
open http://localhost:3000        # macOS
start http://localhost:3000       # Windows
```

---

## Application Pages

| Page | URL | Description |
|---|---|---|
| Dashboard | `/dashboard` | KPI cards — active leases, expiring, maintenance open |
| Leases | `/leases` | 75 seeded leases with Active / Expiring / Renewed / Terminated tabs |
| AI Assistant | `/assistant` | Chat with the LangGraph agent |
| Maintenance | `/maintenance` | 25 maintenance tickets with status and assigned vendor |

---

## Testing the AI Assistant

Open `http://localhost:3000/assistant` and try these prompts in order:

**1. Search for an available unit**
```
Show me available 2-bedroom units in Dubai Marina
```

**2. Look up a tenant**
```
Find tenant Aditya Sharma
```

**3. Ask a RERA policy question** (uses RAG knowledge base)
```
What is the RERA notice period for non-renewal?
```

**4. View expiring leases**
```
Which leases are expiring in the next 90 days?
```

**5. Create a maintenance request**
```
Log a high priority AC maintenance request for unit 304 in Marina Pinnacle for tenant Aditya Sharma
```

**6. Initiate a lease renewal**
```
Start a renewal for lease LSE-2025-000001
```

Each response streams in real time. The agent reasons through tool calls visibly before returning the final answer.

---

## REST API Reference

The full OpenAPI docs are at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/api/v1/leases` | List leases (filter by status, tenant, unit) |
| GET | `/api/v1/leases/{id}` | Lease detail with tenant + unit |
| GET | `/api/v1/tenants` | List tenants |
| GET | `/api/v1/units` | List units (filter by status, type, area) |
| GET | `/api/v1/buildings` | List buildings |
| GET | `/api/v1/maintenance` | List maintenance requests |
| POST | `/api/v1/agent/stream` | Streaming SSE agent endpoint |

---

## Sample Data

The database seeds automatically on first start:

- **10 buildings** across Dubai Marina, Downtown, Business Bay, JVC, Palm Jumeirah
- **100 units** (studios, 1–4BR, penthouses) across all buildings
- **50 tenants** — Indian, Pakistani, British, Filipino, American, Egyptian, Lebanese, French, German nationals
- **75 leases** — 55 active (15 expiring within 90 days), 5 draft, 10 expired, 5 terminated
- **25 maintenance requests** — 10 completed, 10 in-progress/assigned, 5 open

---

## Stopping

```bash
docker-compose down          # stop containers, keep data volumes
docker-compose down -v       # stop and wipe all data (clean slate)
```
