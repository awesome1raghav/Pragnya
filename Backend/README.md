# NEXTRON Backend

Enterprise-grade FastAPI backend service powering the NEXTRON Digital Media Verification and Forensic Analysis Platform.

## Architecture

The backend implements the 18 official NEXTRON domain modules (NexCm through NexRpt), T-MIR orchestration engine, multi-branch forensic execution pipeline, and REST/WebSocket APIs.

## Multi-Model Database Architecture

NEXTRON leverages a dedicated multi-model persistence layer situated in `Backend/Database/`:
- **PostgreSQL (`Database/PostgreSQL/`)**: Relational storage for cases, evidence metadata, analysis findings, audit trails, and transactional models.
- **Neo4j (`Database/Neo4j/`)**: High-performance graph database for evidence node/edge relationships, provenance chains, and cross-media lineage.
- **Qdrant (`Database/Qdrant/`)**: Vector database for deepfake embeddings, multimodal audio/video/image fingerprints, and nearest-neighbor search.
- **Redis (`Database/Redis/`)**: Distributed cache, task queue coordination, and pub/sub event brokers.

## Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start application server
uvicorn App.Main:app --host 0.0.0.0 --port 8000 --reload
```
