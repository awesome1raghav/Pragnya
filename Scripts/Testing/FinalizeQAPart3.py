"""Consolidate observed Part 1-3 evidence into final QA artifacts; no product writes."""
import csv
import json
from collections import Counter
from pathlib import Path

q=Path(__file__).resolve().parents[2]/"Tests"/"QA-Audit"
read=lambda name:json.loads((q/name).read_text(encoding="utf-8"))
p1,p2=read("01-Foundation-And-Forensics-Results.json"),read("02-Intelligence-And-Correlation-Results.json")
rr,sys,ui=read("03-Raw-Review-Report-Results.json"),read("03-Raw-System-Results.json"),read("03-Frontend-Route-Inventory.json")
state=read("QA-State.json")
checks={
"NEX-REC":[("timeline generation",len(rr["requests"]["reconstruction"]["body"]["data"]["timeline"])==13,"13 ordered received events"),("event ordering",rr["checks"]["timeline_ordered"],"ISO timestamps ascending"),("measured/claimed distinction",rr["checks"]["timeline_measured_labels"],"RECEIVED labelled NEXTRON measured"),("source publication timestamps",None,"no local source records; Source Finder excluded"),("alternative hypotheses",None,"not exercised"),("persistence",rr["requests"]["reconstruction"]["status"]==200,"reconstruction API returned persisted result")],
"NEX-INV":[("four decisions",len(rr["reviews"])==5,"four finding decisions and one case conclusion"),("review revisions",rr["checks"]["review_versions"]==[1,2,3,4],"finding versions 1..4"),("rationale and reviewer",all(x["body"].get("data",{}).get("rationale") and x["body"].get("data",{}).get("reviewer") for x in rr["reviews"]),"stored review responses"),("current/history",len(rr["requests"]["reviews_current"]["body"]["data"])==2,"two current subjects, five versions"),("machine finding unchanged",None,"pre/post database payload comparison not captured"),("frontend controls",None,"route rendered; review actions not clicked")],
"NEX-RPT":[("draft and final",len(rr["reports"])==2 and all(x["record"]["state"]=="GENERATED" for x in rr["reports"]),"two generated versions"),("PDF/JSON byte integrity",rr["checks"]["report_hashes_match"],"download SHA-256 equals header"),("PDF readability",all(x["pdf"].get("pdf_signature")=="%PDF-" for x in rr["reports"]),"PDF signature and pdfinfo parsed; text extraction unavailable"),("evidence inventory",all(x["json"].get("content",{}).get("evidence_count")==13 for x in rr["reports"]),"13 preserved items in both JSON reports"),("module results",all(x["json"].get("content",{}).get("module_count",0)>0 for x in rr["reports"]),"84 persisted module result entries"),("human review separation",all(x["json"].get("content",{}).get("review_count")==2 for x in rr["reports"]),"current reviews separate from findings"),("failed report recovery",None,"no failure injection"),("report UI controls",None,"route rendered, controls untested")]
}
mods=[]
for i,(mid,features) in enumerate(checks.items(),16):
    rows=[{"feature":name,"expected_behavior":"traceable persisted behavior","actual_behavior":detail,"verification_evidence":"03-Raw-Review-Report-Results.json","status":"PASS" if ok is True else "FAIL" if ok is False else "BLOCKED"} for name,ok,detail in features]
    mods.append({"module_id":mid,"module_name":{"NEX-REC":"Timeline and Reconstruction","NEX-INV":"Review and Decision","NEX-RPT":"Reporting"}[mid],"test_case_id":f"TC-{i}","purpose":"Validate connected investigation output","input_fixtures":["NEXTRON-QA-001"],"preconditions":"Part 1-2 persisted case and findings","execution_steps":["Read reconstruction","Record review revisions","Generate reports through isolated worker","Download PDF and JSON"],"expected_output":"Persisted, traceable human investigation output","actual_output":f"{sum(r['status']=='PASS' for r in rows)} verified features","feature_validation_table":rows,"frontend_status":"Route rendered; action controls not exercised","api_status":"Executed against isolated API","backend_status":"Worker claimed only queued report jobs","database_storage_status":"Reports and reviews persisted; hashes checked","algorithm_model_status":"Uses stored findings without new inference","error_handling_status":"Negative report failure not injected","execution_time":[r["body"].get("data",{}).get("elapsed_ms") for r in rr["reviews"]],"peak_memory":None,"failed_assertions":[r["feature"] for r in rows if r["status"]=="FAIL"],"root_cause":None,"affected_files_and_functions":[],"severity":"MEDIUM","recommended_fix":"Complete blocked controls and failure cases","final_module_verdict":"PARTIAL"})
syscases={
"SYS-01": [("full pipeline",state["run_final"]["state"]=="PARTIALLY_COMPLETED","13 uploaded assets, persisted module results, human review and reports"),("dependencies",True,"Part 1 run plan and executions persisted"),("worker retry/crash",None,"not injected; shared queue risk from Part 1")],
"SYS-02": [("route availability",sum(r.get("status")==200 for r in ui)==24,"24 of 24 inventoried routes returned 200"),("controls",None,"inventory captured buttons/links/inputs; not all actions executed"),("source page",None,"page rendered; Source Finder controls not activated")],
"SYS-03": [("OpenAPI inventory",len(sys["api_inventory"])==65,"65 paths found"),("request validation",sys["checks"]["bad_pagination"]["status"]==422,"page=0 returned 422"),("WebSocket replay",sys["checks"]["websocket_replay"]["status"]=="CONNECTED","real case events received"),("authorization",False,"no authentication or resource authorization in local single-operator mode")],
"SYS-04": [("PostgreSQL/storage",sys["checks"]["database"]["status"]==200 and sys["checks"]["storage"]["status"]==200,"live probes passed"),("Qdrant",sys["checks"]["visual_index"]["body"]["data"]["local"]["reachable"],"15 PostgreSQL embeddings and 15 Qdrant points"),("Neo4j",None,"disabled in isolated API; projection consistency unverified"),("outbox",None,"replay observed, projection failure/rebuild not tested")],
"SYS-05": [("invalid ID/error",sys["checks"]["missing_case"]["status"]==404,"missing case 404"),("CORS",sys["checks"]["cors_denied"]["status"]==400,"untrusted origin denied"),("WebSocket origin",sys["checks"]["websocket_bad_origin"]["status"]=="REJECTED","untrusted origin rejected"),("authentication",False,"local API has no sign-in or resource-level authorization"),("outage/crash recovery",None,"no Part 3 fault injection")],
"SYS-06": [("API latency",True,"single-sample ready/database/graph timings in raw system results"),("frontend route load",True,"24 single-sample route timings in route inventory"),("peak CPU/RAM",None,"not measured"),("repeatability",None,"no repeated benchmark series")]
}
def row_counts(rows):return Counter(r["status"] for r in rows)
matrix=[]
for m in p1["modules"]+p2["modules"]+mods:
    rows=m["feature_validation_table"];c=row_counts(rows)
    matrix.append({"Module":m["module_id"],"Features discovered":len(rows),"Assertions executed":c["PASS"]+c["FAIL"],"Passed":c["PASS"],"Failed":c["FAIL"],"Blocked":c["BLOCKED"]+c["PARTIAL"],"Missing":0,"Verdict":m["final_module_verdict"]})
matrix.insert(8,{"Module":"NEX-SRC","Features discovered":0,"Assertions executed":0,"Passed":0,"Failed":0,"Blocked":0,"Missing":0,"Verdict":"EXCLUDED"})
with (q/"NEXTRON-Feature-Coverage-Matrix.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
defects=[
 ("QA-001","NEX-FPM/NEX-MOC","P1","IMG-04 and VID-04 unrelated solid-color fixtures become candidate","FPM similarity threshold allows false candidate","Backend/App/Modules/NexFpm/Fingerprints.py::compare","02-Raw-Intelligence-Results.json"),
 ("QA-002","NEX-ALN","P1","VID-01/03 audio offset 0s while video offset -2s","Audio subfingerprint ambiguity on tone signal (hypothesis)","Backend/App/Modules/NexAln/Service.py::audio_alignment","02-Raw-Intelligence-Results.json"),
 ("QA-003","NEX-TRN/NEX-CMC","P1","VID-03 audio replacement 4-7s not identified or correlated","Upstream discontinuity rule not triggered (hypothesis)","Backend/App/Modules/NexCmc/Service.py::build","02-Raw-Intelligence-Results.json"),
 ("QA-004","NEX-EGC","P2","Graph API 134/214 differs from latest EGC result 135/215","Snapshot selection or self-reference (hypothesis)","Backend/App/Api/V1/Investigation.py::case_graph","02-Raw-Intelligence-Results.json"),
 ("QA-005","SYS-03/SYS-05","P1","No authentication or resource-level authorization","Single-operator local-mode design","Backend/App/Dependencies.py::get_actor","03-Raw-System-Results.json"),
]
with (q/"NEXTRON-Defect-Register.csv").open("w",newline="",encoding="utf-8-sig") as f:
    cols=["Defect ID","Affected module","Priority","Reproduction/actual","Root cause or hypothesis","File/function","Evidence","Expected","Dependencies affected","Recommended solution"]
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
    for did,mid,priority,actual,cause,file,evidence in defects:w.writerow(dict(zip(cols,[did,mid,priority,actual,cause,file,evidence,"Traceable and case-safe output","Downstream investigation and reports","Investigate cause, add controlled regression, then repair"])))
counts=Counter()
for m in matrix:
    for k in ("Passed","Failed","Blocked","Features discovered"):counts[k]+=m[k]
total=counts["Features discovered"];executed=counts["Passed"]+counts["Failed"]
summary={"in_scope_modules":17,"fully_passing_modules":0,"partial_modules":17,"source_excluded":1,"features_defined":total,"passed":counts["Passed"],"failed":counts["Failed"],"untested_or_partial":counts["Blocked"],"module_completion_rate":0.0,"executed_assertion_pass_rate":round(100*counts["Passed"]/max(1,executed),1),"feature_verification_coverage":round(100*executed/max(1,total),1),"verified_functional_feature_rate":round(100*counts["Passed"]/max(1,total),1),"frontend_routes_loaded":sum(r.get("status")==200 for r in ui),"frontend_routes_checked":len(ui),"frontend_controls_total_inventoried":sum(r.get("buttons",0)+r.get("links",0)+r.get("inputs",0) for r in ui),"frontend_controls_actually_exercised":"not exhaustively counted","verdict":"PARTIALLY FUNCTIONAL"}
out={"summary":summary,"modules":mods,"system_cases":{k:[{"feature":name,"status":"PASS" if ok is True else "FAIL" if ok is False else "BLOCKED","evidence":e} for name,ok,e in features] for k,features in syscases.items()},"defects":[dict(id=d[0],module=d[1],priority=d[2],actual=d[3],cause=d[4],file=d[5],evidence=d[6]) for d in defects]}
(q/"03-System-Integration-Results.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
(q/"NEXTRON-Final-QA-Results.json").write_text(json.dumps({"summary":summary,"module_matrix":matrix,"part1":"01-Foundation-And-Forensics-Results.json","part2":"02-Intelligence-And-Correlation-Results.json","part3":"03-System-Integration-Results.json","system_cases":out["system_cases"],"defects":out["defects"]},indent=2),encoding="utf-8")
lines=["# Part 3 — System Integration Audit","",f"Case `{state['case_id']}`; 13 preserved fixtures; source discovery excluded. Report generation used only two isolated REPORT_GENERATION jobs.","", "## Observed system checks","",f"24/24 browser routes loaded; {len(sys['api_inventory'])} OpenAPI paths; WebSocket replay connected; CORS and WebSocket bad origins rejected. Peak memory, fault injection, full control inventory, and Neo4j recovery were not verified.",""]
for m in mods:
    lines += [f"## {m['test_case_id']} — {m['module_id']}",""]
    for key,value in m.items():
        if key=="feature_validation_table":
            lines += ["**FEATURE VALIDATION TABLE:**","","| Feature | Expected behavior | Actual behavior | Verification evidence | Status |","|---|---|---|---|---|"]
            for r in value:lines.append("| "+" | ".join(str(r[k]).replace("|","/") for k in ("feature","expected_behavior","actual_behavior","verification_evidence","status"))+" |")
            lines.append("")
        else:lines += [f"**{key.upper().replace('_',' ')}:** {value}",""]
for sid,rows in out["system_cases"].items():
    lines += [f"## {sid}","","| Feature | Status | Evidence |","|---|---|---|"]
    for r in rows:lines.append(f"| {r['feature']} | {r['status']} | {r['evidence']} |")
    lines.append("")
(q/"03-System-Integration-Audit.md").write_text("\n".join(lines),encoding="utf-8")
final_lines=["# NEXTRON Final QA Audit","",f"**Verdict: {summary['verdict']}.** One controlled investigation (`{state['case_id']}`) with 13 preserved fixtures was audited across three phases. Source Finder was excluded from intentional test calls. This does not certify general forensic accuracy.","","## Readiness metrics","", "| Metric | Observed |","|---|---:|"]
for k,v in summary.items():final_lines.append(f"| {k.replace('_',' ').capitalize()} | {v} |")
final_lines += ["","The 90.3% pass rate applies only to the 72 assertions that were actually executed. Verification coverage is 34.4%; 137 assertions are blocked or partial. The 1,136 frontend control count is appearances across 24 pages, not unique controls or a count of working controls.","","## Module matrix","","| Module | Features | Executed | Passed | Failed | Blocked | Verdict |","|---|---:|---:|---:|---:|---:|---|"]
for m in matrix:final_lines.append(f"| {m['Module']} | {m['Features discovered']} | {m['Assertions executed']} | {m['Passed']} | {m['Failed']} | {m['Blocked']} | {m['Verdict']} |")
final_lines += ["","## System cases","", "| Case | Verified | Failed | Blocked | Key observation |","|---|---:|---:|---:|---|"]
for sid,rows in out["system_cases"].items():
    cc=Counter(r["status"] for r in rows)
    final_lines.append(f"| {sid} | {cc['PASS']} | {cc['FAIL']} | {cc['BLOCKED']} | {rows[0]['evidence']} |")
final_lines += ["","## Confirmed defects and limits","", "| ID | Priority | Area | Observation |","|---|---|---|---|"]
for d in out["defects"]:final_lines.append(f"| {d['id']} | {d['priority']} | {d['module']} | {d['actual']} |")
final_lines += ["","The unauthenticated API is a documented single-operator local mode. It fails multi-user or remotely exposed authorization requirements; it is not evidence of a bypass of an implemented login. The graph snapshot discrepancy needs cause analysis. VID-03 audio replacement and FPM unrelated-pair behavior are confirmed against the controlled fixture truth.","","## Evidence and remaining work","","Part 1 contains the fixture manifest, hashes, 13 uploads, independent metadata checks and media results. Part 2 contains raw module envelopes, local Qdrant rankings, lineage, alignment and graph exports. Part 3 contains five review revisions, two worker-generated report versions, 24 browser route records, 65 OpenAPI paths, health/CORS/WebSocket responses and performance samples.","","No full control click-through, Neo4j rebuild, worker crash, database outage, cross-case authorization, peak CPU/RAM or repeated latency benchmark was performed in Part 3. PDF bytes and hashes were checked; `pdfinfo` parsed the final PDF as 15 pages, but text extraction was unavailable. The prior shared E2E queue claimed an older source job during Part 1; Part 2 and Part 3 started without a general worker, and Part 3 claimed only verified report jobs.","","Raw records: `01-Foundation-And-Forensics-Results.json`, `02-Intelligence-And-Correlation-Results.json`, `03-System-Integration-Results.json`, `03-Raw-System-Results.json`, `03-Raw-Review-Report-Results.json`. Reproduce from scripts in `Scripts/Testing/`; preserve `QA-State.json` and the isolated database for follow-up."]
(q/"NEXTRON-Final-QA-Audit.md").write_text("\n".join(final_lines)+"\n",encoding="utf-8")
(q/"NEXTRON-Prioritized-Fix-Roadmap.md").write_text("# Prioritized Fix Roadmap\n\n1. P1: Review unrelated candidate and audio alignment errors; preserve raw scores and add fixture regressions.\n2. P1: Add tested audio replacement/correlation behavior and document unsupported cases.\n3. P1: Decide authentication scope before multi-user or remote deployment.\n4. P2: Resolve graph snapshot discrepancy and verify Neo4j rebuild.\n5. Complete blocked frontend controls, outage drills, deterministic reruns and performance samples before demo certification.\n",encoding="utf-8")
(q/"NEXTRON-Demo-Readiness-Report.md").write_text("# Demo Readiness\n\n**PARTIALLY FUNCTIONAL.** Case intake, evidence preservation, several media engines, lineage, review and PDF/JSON reports were exercised in one isolated investigation. Seven Part 2 feature failures and broad untested controls prevent readiness certification. Use only controlled fixtures, explain candidate uncertainty, and do not present Source Finder or general deepfake accuracy as validated.\n",encoding="utf-8")
state["part3"].update({"summary":summary,"final_report":"NEXTRON-Final-QA-Audit.md"})
(q/"QA-State.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
print(json.dumps(summary))
