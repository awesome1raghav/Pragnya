"""Safe readback and negative checks against isolated API; excludes source discovery."""
import asyncio
import json
import time
from pathlib import Path

import httpx
import websockets

root = Path(__file__).resolve().parents[2] / "Tests" / "QA-Audit"
state = json.loads((root / "QA-State.json").read_text(encoding="utf-8"))
cid = state["case_id"]
b = "http://127.0.0.1:8002"
client = httpx.Client(base_url=b, timeout=10)
out = {"case_id":cid,"checks":{},"api_inventory":[],"latencies_ms":{}}
spec = client.get("/openapi.json").json()
out["api_inventory"] = [{"path":p,"methods":list(v)} for p,v in spec["paths"].items()]

def check(name,method,path,**kw):
    start=time.perf_counter(); r=client.request(method,path,**kw)
    out["latencies_ms"][name]=round((time.perf_counter()-start)*1000,2)
    out["checks"][name]={"status":r.status_code,"body":r.json() if r.headers.get("content-type","").startswith("application/json") else None}

for name,path in {"health":"/api/v1/health","ready":"/api/v1/health/ready","database":"/api/v1/system/database","storage":"/api/v1/system/storage","visual_index":"/api/v1/visual-search/status","case":f"/api/v1/cases/{cid}","evidence":f"/api/v1/cases/{cid}/evidence","jobs":f"/api/v1/jobs?case_id={cid}","lineage":f"/api/v1/cases/{cid}/lineage","graph":f"/api/v1/cases/{cid}/graph","reconstruction":f"/api/v1/cases/{cid}/reconstruction","reviews":f"/api/v1/cases/{cid}/reviews","reports":f"/api/v1/cases/{cid}/reports","missing_case":"/api/v1/cases/00000000-0000-0000-0000-000000000000","bad_pagination":"/api/v1/cases?page=0"}.items():
    check(name,"GET",path)
check("cors_allowed","OPTIONS","/api/v1/cases",headers={"Origin":"http://localhost:8090","Access-Control-Request-Method":"POST"})
check("cors_denied","OPTIONS","/api/v1/cases",headers={"Origin":"http://untrusted.invalid","Access-Control-Request-Method":"POST"})
check("missing_evidence","GET","/api/v1/evidence/00000000-0000-0000-0000-000000000000")

async def ws():
    url=f"ws://127.0.0.1:8002/api/v1/ws/cases/{cid}?after=0"
    try:
        async with websockets.connect(url,origin="http://localhost:8090",open_timeout=5) as sock:
            msgs=[]
            for _ in range(3):
                msg=json.loads(await asyncio.wait_for(sock.recv(),timeout=5))
                msgs.append({k:msg.get(k) for k in ("type","sequence","event_type","case_id")})
                if msg.get("type")=="replay_complete": break
            out["checks"]["websocket_replay"]={"status":"CONNECTED","messages":msgs}
    except Exception as exc:
        out["checks"]["websocket_replay"]={"status":"ERROR","error":type(exc).__name__+": "+str(exc)[:150]}
    try:
        async with websockets.connect(url,origin="http://untrusted.invalid",open_timeout=5) as sock:
            await asyncio.wait_for(sock.recv(),timeout=2)
            out["checks"]["websocket_bad_origin"]={"status":"ACCEPTED"}
    except Exception as exc:
        out["checks"]["websocket_bad_origin"]={"status":"REJECTED","error":type(exc).__name__}
asyncio.run(ws())
(root/"03-Raw-System-Results.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps({"api_paths":len(out["api_inventory"]),"websocket":out["checks"]["websocket_replay"]["status"],"bad_origin":out["checks"]["websocket_bad_origin"]["status"],"latency_ms":{k:out["latencies_ms"][k] for k in ("ready","database","graph")}}))
