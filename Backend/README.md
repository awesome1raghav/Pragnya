# NEXTRON Backend

Enterprise-grade FastAPI backend service powering the NEXTRON Digital Media Verification and Forensic Analysis Platform.

## Architecture

The backend implements the 18 official NEXTRON domain modules (NexCm through NexRpt), T-MIR orchestration engine, multi-branch forensic execution pipeline, and REST/WebSocket APIs.

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
