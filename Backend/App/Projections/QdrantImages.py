"""Qdrant ANN projection: deterministic points, case filter, PostgreSQL-backed recovery."""

import uuid

import httpx

from Backend.App.Modules.NexFpm.Embeddings import DIMENSIONS, MODEL_KEY

COLLECTION = "nextron_images_siglip2_b16_224_v1"


class QdrantImages:
    def __init__(self, url: str, api_key: str = ""):
        self.url = url.rstrip("/")
        self.headers = {"api-key": api_key} if api_key else {}

    def _request(self, method, path, json=None):
        with httpx.Client(base_url=self.url, headers=self.headers, timeout=httpx.Timeout(20, connect=3)) as client:
            response = client.request(method, path, json=json)
            response.raise_for_status()
            return response.json()

    def ensure(self):
        try:
            self._request("GET", f"/collections/{COLLECTION}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            self._request("PUT", f"/collections/{COLLECTION}",
                          {"vectors": {"size": DIMENSIONS, "distance": "Cosine"}})
        try:
            self._request("PUT", f"/collections/{COLLECTION}/index", {"field_name": "case_id", "field_schema": "keyword"})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 409:
                raise

    def upsert(self, rows):
        rows = list(rows)
        if not rows:
            return
        self._request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": [
            {"id": str(row.evidence_id), "vector": row.vector,
             "payload": {"case_id": str(row.case_id), "evidence_id": str(row.evidence_id), "model_key": MODEL_KEY}}
            for row in rows]})

    def query(self, vector: list[float], case_id: uuid.UUID, limit: int):
        result = self._request("POST", f"/collections/{COLLECTION}/points/query", {
            "query": vector, "limit": limit, "with_payload": True,
            "filter": {"must": [{"key": "case_id", "match": {"value": str(case_id)}},
                                {"key": "model_key", "match": {"value": MODEL_KEY}}]},
        })
        return result["result"]["points"]

    def count(self) -> int:
        return int(self._request("GET", f"/collections/{COLLECTION}")["result"]["points_count"])
