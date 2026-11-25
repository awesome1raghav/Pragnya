/* UI vocabulary for the contract's enums: every label and colour the screens show lives here,
   so the backend only ever sends snake_case values. Data itself comes from ./store (via ./api). */
import type { Branch, CaseStatus, EdgeKind, FindingStatus, GraphNode, Severity } from './api';

export type Tone = 'gold' | 'alert' | 'steel' | 'ok' | 'mute' | 'ink';
export type View = 'command' | 'investigate' | 'graph' | 'intake' | 'report' | 'audit';
export type Tool = 'viewer' | 'frames' | 'timeline' | 'metadata';

export const statusLabel: Record<CaseStatus, string> = { flagged: 'Flagged', in_review: 'In review', active: 'Active', on_hold: 'On hold', verified: 'Verified' };
export const statusTone: Record<CaseStatus, Tone> = { flagged: 'alert', in_review: 'steel', active: 'ink', on_hold: 'mute', verified: 'ok' };
export const severityTone: Record<Severity, Tone> = { high: 'alert', medium: 'steel', low: 'mute', info: 'ok' };
export const findingStatusLabel: Record<FindingStatus, string> = { open: 'Open', accepted: 'Accepted', rejected: 'Rejected', second_review: 'Second review' };
export const BRANCHES: Branch[] = ['spatial', 'temporal', 'audio_visual', 'provenance'];
export const branchLabel: Record<Branch, string> = { spatial: 'Spatial', temporal: 'Temporal', audio_visual: 'Audio-visual', provenance: 'Provenance' };
export const branchColor: Record<Branch, string> = { spatial: '#e9a23b', temporal: '#d9652b', audio_visual: '#7fa6bf', provenance: '#8fbf7a' };
export const toneColor: Record<Tone, string> = { gold: '#e9a23b', alert: '#f0604d', steel: '#7fa6bf', ok: '#8fbf7a', mute: '#8d877c', ink: '#bdb6aa' };

export const edgeStyle: Record<EdgeKind, { label: string; tone: Tone; dash?: string }> = {
  contains: { label: 'Belongs to', tone: 'mute' },
  pattern: { label: 'Shared manipulation pattern', tone: 'alert', dash: '6 5' },
  timestamp: { label: 'Conflicting timestamps', tone: 'gold', dash: '2 4' },
  metadata: { label: 'Metadata relationship', tone: 'steel' },
  derived: { label: 'Same source', tone: 'ok' },
};
export const nodeTone = (n: GraphNode): Tone => n.severity ? severityTone[n.severity] : n.status ? statusTone[n.status] : 'mute';

export const timeOf = (iso: string) => { const d = new Date(iso); const today = new Date('2025-01-26T23:59:59Z'); const days = Math.floor((today.getTime() - d.getTime()) / 864e5); return days < 1 ? d.toISOString().slice(11, 16) : days < 2 ? 'Yesterday' : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }); };
export const mb = (n: number) => n >= 1073741824 ? `${(n / 1073741824).toFixed(2)} GB` : `${(n / 1048576).toFixed(1)} MB`;
