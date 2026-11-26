"""Replay authoritative PostgreSQL embeddings into Qdrant after loss or model upgrade."""

from sqlalchemy import select

from Backend.App.Config import get_settings
from Backend.App.Modules.NexFpm.Embeddings import MODEL_KEY
from Backend.App.Projections.QdrantImages import QdrantImages
from Database.PostgreSQL.Connection import EngineOptions, create_database_engine
from Database.PostgreSQL.Models import VisualEmbedding
from Database.PostgreSQL.Session import create_session_factory


def main():
    settings = get_settings()
    if not settings.QDRANT_URL:
        raise SystemExit("QDRANT_URL is not set")
    index = QdrantImages(settings.QDRANT_URL, settings.QDRANT_API_KEY.get_secret_value())
    index.ensure()
    engine = create_database_engine(settings.DATABASE_URL, EngineOptions(pooled=False))
    count = 0
    try:
        with create_session_factory(engine)() as session:
            for offset in range(0, 2**31, 128):
                rows = list(session.scalars(select(VisualEmbedding).where(VisualEmbedding.model_key == MODEL_KEY)
                                            .order_by(VisualEmbedding.id).offset(offset).limit(128)))
                if not rows:
                    break
                index.upsert(rows)
                count += len(rows)
    finally:
        engine.dispose()
    print(f"Rebuilt {count} image vectors from PostgreSQL")


if __name__ == "__main__":
    main()
