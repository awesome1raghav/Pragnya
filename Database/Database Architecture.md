# NEXTRON Multi-Model Database Architecture

## 1. Source of Truth Principle
- **PostgreSQL**: Authoritative store for cases, evidence metadata, analysis findings, jobs, reviews, reports, and tamper-evident audit logs.
- **Neo4j**: Rebuildable projection for media relationships, face-track clusters, and multimodal lineage traversal.
- **Qdrant**: Rebuildable projection for high-dimensional forensic embeddings and nearest-neighbor similarity search.
- **Redis**: Distributed cache and task coordination.
