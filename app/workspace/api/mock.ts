/* Mock adapter: the whole contract, in memory, with realistic latency. Mutations persist for the session
   (accept a finding, upload a file, run an analysis) so every flow can be demoed end to end offline. */
import type { AnalysisJob, Evidence, Finding, NextronApi } from './contract';
import * as fx from './fixtures';

const wait = (ms: number) => new Promise(r => setTimeout(r, ms + Math.random() * ms * .4));
const clone = <T,>(v: T): T => structuredClone(v);
const db = { cases: clone(fx.cases), evidence: clone(fx.evidence), findings: clone(fx.findings), decisions: clone(fx.decisions), activity: clone(fx.activity), audit: clone(fx.audit) };
const jobs = new Map<string, { job: AnalysisJob; started: number }>();
const STAGES = [['verify', 'Verify sealed hash'], ['sample', 'Sample frames and track faces'], ['branches', 'Spatial, temporal and audio-visual branches'], ['fuse', 'Fuse evidence']];
const STAGE_MS = 650;

function tick(id: string): AnalysisJob {
  const entry = jobs.get(id)!; const { job } = entry;
  const t = (Date.now() - entry.started) / STAGE_MS;
  const done = Math.min(STAGES.length, Math.floor(t));
  job.stages = job.stages.map((s, i) => ({ ...s, state: i < done ? 'done' : i === done ? 'running' : 'waiting' }));
  job.progress = Math.min(1, t / STAGES.length);
  if (done >= STAGES.length) { job.state = 'done'; job.findings = clone(db.findings.filter(f => f.evidenceId === job.evidenceId)); }
  else job.state = t < .2 ? 'queued' : 'running';
  return clone(job);
}

export const mockApi: NextronApi = {
  async listCases() { await wait(140); return clone(db.cases); },
  async listEvidence(caseId) { await wait(120); return clone(db.evidence.filter(e => !caseId || e.caseId === caseId)); },
  async listFindings(f) {
    await wait(120);
    const evIds = f?.caseId ? db.evidence.filter(e => e.caseId === f.caseId).map(e => e.id) : null;
    return clone(db.findings.filter(x => (!f?.evidenceId || x.evidenceId === f.evidenceId) && (!evIds || evIds.includes(x.evidenceId))));
  },
  async updateFinding(id, status) { await wait(120); const x = db.findings.find(f => f.id === id)!; x.status = status; return clone(x); },
  async getGraph() { await wait(160); return clone(fx.graph); },
  async getAssessment(caseId) { await wait(100); return clone(fx.assessments[caseId] ?? { caseId, outcomes: [], note: 'No fused assessment yet.' }); },
  async listDecisions() { await wait(110); return clone(db.decisions); },
  async decide(id, action) {
    await wait(140);
    const d = db.decisions.find(x => x.id === id); db.decisions = db.decisions.filter(x => x.id !== id);
    if (d?.findingId && (action === 'accept' || action === 'resolve')) { const f = db.findings.find(x => x.id === d.findingId); if (f) f.status = 'accepted'; }
  },
  async listActivity() { await wait(100); return clone(db.activity); },
  async listAudit() { await wait(120); return clone(db.audit); },
  async listModels() { await wait(80); return clone(fx.models); },
  async uploadEvidence({ caseId, file, sha256 }, onProgress) {
    for (let p = 0; p <= 1; p += .2) { onProgress?.(p); await wait(90); }
    const id = `EV-${String(200 + db.evidence.length).padStart(4, '0')}`;
    const e: Evidence = { id, caseId, fileName: file.name, kind: file.type.startsWith('image/') ? 'image' : 'video', status: 'active', durationSec: 0, source: 'Uploaded by R. Carter', capturedAt: new Date().toISOString(), sha256, sizeBytes: file.size, width: 1280, height: 757, codec: file.type || 'unknown', media: fx.media('rain-street'), metadata: [{ key: 'Uploaded', value: new Date().toUTCString() }] };
    db.evidence.push(e); return clone(e);
  },
  async startAnalysis(evidenceId) {
    await wait(120);
    const id = `JOB-${Date.now().toString(36)}`;
    jobs.set(id, { started: Date.now(), job: { id, evidenceId, state: 'queued', progress: 0, stages: STAGES.map(([key, label]) => ({ key, label, state: 'waiting' })) } });
    return tick(id);
  },
  async getAnalysis(jobId) { await wait(60); return tick(jobId); },
};
export type { Finding };
