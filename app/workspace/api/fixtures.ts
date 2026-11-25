/* Demo data in contract shapes. Used only by the mock adapter; delete nothing here when the real API
   lands, it keeps the UI demoable offline. Imagery: licensed stand-ins (see CREDITS) graded as CCTV stills. */
import type { ActivityItem, Assessment, AuditEvent, Case, Decision, Evidence, Finding, Graph, GraphEdge, GraphNode, Media, MetadataField, ModelInfo } from './contract';

const SIZE: Record<string, [number, number]> = {
  interview: [900, 1125], 'aerial-road': [960, 1433], 'harbor-ships': [1280, 719], 'rain-street': [1280, 757], 'rain-window': [1280, 962],
  'station-concourse': [1280, 917], escalator: [1280, 853], 'fjord-facility': [1280, 853], 'lobby-silhouette': [1280, 853], 'night-street': [1280, 853], 'station-platform': [1280, 853],
};
export const media = (key: string): Media => ({
  still: `/images/evidence/${key}-1280.webp`, thumb: `/images/evidence/${key}-480.webp`, overlay: `/images/evidence/${key}-ela.webp`,
  width: SIZE[key][0], height: SIZE[key][1], ...(key === 'interview' ? { focus: { x: .5, y: .3 } } : {}),
});

export const CREDITS = 'Stand-in footage: Nicolai Berntsen, Matthew Wiebe, Israel Sundseth, Noah Kuhn, John Maravelakis, Thong Vo, Riley Briggs, Sam X (Unsplash License); Todd Diemer (CC0) and Ximonic (CC BY-SA 4.0) via Wikimedia Commons. Interview portrait generated for this demo.';

const r = (s: number, t: number, a: number, p: number) => ({ spatial: s, temporal: t, audio_visual: a || null, provenance: p });
export const cases: Case[] = [
  { id: 'NX-10487', name: 'Corvane interview clip', summary: 'Suspected face swap in a recorded broadcast interview', status: 'flagged', priority: 96, reason: 'Two high-severity findings are waiting for your decision.', analyst: 'R. Carter', updatedAt: '2025-01-26T14:06:00Z', legalHold: true, cover: media('interview'), readiness: r(92, 78, 61, 84) },
  { id: 'NX-10486', name: 'Harbor convoy sighting', summary: 'Vessel footage and the location claims made with it', status: 'in_review', priority: 71, reason: 'Timestamps from two uploads disagree by 41 minutes.', analyst: 'S. Moran', updatedAt: '2025-01-26T13:41:00Z', legalHold: false, cover: media('harbor-ships'), readiness: r(80, 66, 0, 72) },
  { id: 'NX-10483', name: 'Central station crowd', summary: 'Crowd-size claims in a widely shared concourse video', status: 'active', priority: 58, reason: 'Possible duplicated figures in the left third of the frame.', analyst: 'R. Carter', updatedAt: '2025-01-26T12:02:00Z', legalHold: false, cover: media('station-concourse'), readiness: r(70, 64, 52, 60) },
  { id: 'NX-10479', name: 'Fjord facility expansion', summary: 'Drone imagery compared against earlier survey passes', status: 'active', priority: 44, reason: 'Two new pens appear between passes; provenance checks out.', analyst: 'L. Chen', updatedAt: '2025-01-26T11:03:00Z', legalHold: false, cover: media('fjord-facility'), readiness: r(91, 88, 0, 93) },
  { id: 'NX-10476', name: 'Riverside depot, night', summary: 'Competing CCTV claims about a vehicle at the gate', status: 'on_hold', priority: 30, reason: 'Waiting for the depot to send the original recorder export.', analyst: 'D. Arden', updatedAt: '2025-01-25T17:20:00Z', legalHold: false, cover: media('night-street'), readiness: r(52, 40, 0, 45) },
  { id: 'NX-10471', name: 'Platform 6 incident', summary: 'Platform CCTV continuity for a reported assault', status: 'verified', priority: 12, reason: 'Verified authentic. The report is signed and filed.', analyst: 'R. Carter', updatedAt: '2025-01-19T09:12:00Z', legalHold: false, cover: media('station-platform'), readiness: r(100, 100, 100, 100) },
];

const meta = (device: string, created: string, encoder: string, conflict = false): MetadataField[] => [
  { key: 'Device', value: device }, { key: 'Created', value: created },
  { key: 'Modified', value: conflict ? '2025-01-24 22:41:07 UTC' : created, conflict, note: conflict ? 'Written three days after the camera created the file' : undefined },
  { key: 'Encoder', value: encoder, conflict, note: conflict ? 'Camera files are written by the camera, not by FFmpeg' : undefined },
  { key: 'GPS', value: 'Not present' }, { key: 'Colour space', value: 'BT.709' }, { key: 'Frame rate', value: '30.000 fps' },
];
const ev = (id: string, caseId: string, fileName: string, kind: Evidence['kind'], key: string, status: Evidence['status'], durationSec: number, source: string, capturedAt: string, sha256: string, sizeBytes: number, codec: string, m: MetadataField[]): Evidence =>
  ({ id, caseId, fileName, kind, status, durationSec, source, capturedAt, sha256, sizeBytes, width: kind === 'image' ? 4032 : 1920, height: kind === 'image' ? 3024 : 1080, codec, media: media(key), metadata: m });

export const evidence: Evidence[] = [
  ev('EV-0194', 'NX-10487', 'interview_clip.mp4', 'video', 'interview', 'flagged', 48, 'Broadcast upload', '2025-01-21T18:02:14Z', '9f4e2a6b8d9c7d0f6a3b1e9a2b7d4e5f8c9d0a1b', 883_532_595, 'H.264 / AAC', meta('Sony FX3', '2025-01-21 18:02:14 UTC', 'Lavf 60.3.100 (FFmpeg)', true)),
  ev('EV-0195', 'NX-10487', 'lobby_cam_02.mp4', 'video', 'lobby-silhouette', 'in_review', 120, 'Studio lobby CCTV', '2025-01-21T17:55:00Z', '3c1a77e0b29f4d1c88a0e5f2c1d93b7a6e0f4d21', 327_155_712, 'H.264', meta('Hikvision DS-2CD', '2025-01-21 17:55:00 UTC', 'Hikvision NVR 4.1')),
  ev('EV-0196', 'NX-10487', 'street_cam_03.mp4', 'video', 'rain-street', 'verified', 90, 'City camera, Kerr St', '2025-01-21T17:48:30Z', 'a8e3f1c09d2b6e47f0c3a9d18e5b72c4f6a1d0e9', 208_037_478, 'H.265', meta('Axis Q1798', '2025-01-21 17:48:30 UTC', 'Axis OS 11.8')),
  ev('EV-0197', 'NX-10487', 'escalator_cam.mp4', 'video', 'escalator', 'verified', 60, 'Transit authority', '2025-01-21T17:40:12Z', 'e71b4c0a9f3d28e6c1a5f0b93d7e2c48a6f1b0d3', 148_793_754, 'H.264', meta('Bosch Flexidome', '2025-01-21 17:40:12 UTC', 'Bosch VRM 4.0')),
  ev('EV-0198', 'NX-10487', 'window_still.jpg', 'image', 'rain-window', 'in_review', 0, 'Witness phone', '2025-01-21T18:10:44Z', '5d0c9e2a7b4f61c3e8a0d91f2b6c47e3a9f0c1d8', 4_404_019, 'JPEG', meta('iPhone 14 Pro', '2025-01-21 18:10:44 UTC', 'Apple iOS 17.2')),
  ev('EV-0199', 'NX-10487', 'drone_pass.mov', 'video', 'aerial-road', 'verified', 75, 'News drone', '2025-01-21T18:20:03Z', 'b2f7a0c4e91d3e68a5c0f1b7d2e94c3a6f0b8d15', 1_181_116_006, 'ProRes 422', meta('DJI Mavic 3', '2025-01-21 18:20:03 UTC', 'DJI 01.01.0300')),
  ev('EV-0140', 'NX-10486', 'harbor_ships.mp4', 'video', 'harbor-ships', 'in_review', 60, 'Harbour authority', '2025-01-21T09:10:00Z', '4a1f2e9d0c7f1a3b5e8d6c4a2f0e9b7d5c3a1f8e', 230_686_720, 'H.264', meta('Axis P1468', '2025-01-21 09:10:00 UTC', 'Axis OS 11', true)),
  ev('EV-0149', 'NX-10483', 'station_concourse.mp4', 'video', 'station-concourse', 'active', 75, 'Shared social video', '2025-01-22T09:11:00Z', 'c09e2e9d0c7f1a3b5e8d6c4a2f0e9b7d5c3a1f8e', 321_912_832, 'H.264', meta('Unknown (re-encoded)', '2025-01-22 09:11:00 UTC', 'Lavf 59 (FFmpeg)', true)),
  ev('EV-0158', 'NX-10479', 'fjord_facility.mp4', 'video', 'fjord-facility', 'active', 90, 'Survey drone', '2025-01-23T09:12:00Z', '7d3b2e9d0c7f1a3b5e8d6c4a2f0e9b7d5c3a1f8e', 413_138_944, 'H.265', meta('DJI Mavic 3', '2025-01-23 09:12:00 UTC', 'DJI 01.01')),
  ev('EV-0167', 'NX-10476', 'night_street.mp4', 'video', 'night-street', 'on_hold', 105, 'Depot CCTV', '2025-01-24T21:13:00Z', 'e2a82e9d0c7f1a3b5e8d6c4a2f0e9b7d5c3a1f8e', 504_365_056, 'H.264', meta('Dahua IPC', '2025-01-24 21:13:00 UTC', 'Dahua 3.0')),
  ev('EV-0176', 'NX-10471', 'station_platform.mp4', 'video', 'station-platform', 'verified', 120, 'Platform CCTV', '2025-01-18T22:40:00Z', '0b6c2e9d0c7f1a3b5e8d6c4a2f0e9b7d5c3a1f8e', 595_591_168, 'H.264', meta('Bosch Flexidome', '2025-01-18 22:40:00 UTC', 'Bosch VRM 4')),
];

const M = { name: 'NX-ANL', version: '2.4.1' };
export const findings: Finding[] = [
  { id: 'F-021', evidenceId: 'EV-0194', branch: 'spatial', severity: 'high', status: 'open', confidence: .91, title: 'Blending seam along the left jaw', detail: 'Texture and lighting along the jawline differ from the cheek above it, the typical edge of a swapped face.', startSec: 22.4, endSec: 26.1, region: { x: 30, y: 54, w: 22, h: 18 }, explanations: [{ label: 'Face swap', likelihood: .74 }, { label: 'Beauty filter', likelihood: .18 }, { label: 'Compression edge', likelihood: .08 }], model: M },
  { id: 'F-022', evidenceId: 'EV-0194', branch: 'temporal', severity: 'high', status: 'open', confidence: .88, title: 'Frames 712 to 724 replaced', detail: 'Motion vectors break for 12 frames, then return to the earlier path. No scene cut explains the break.', startSec: 23.7, endSec: 24.1, region: { x: 20, y: 18, w: 60, h: 66 }, explanations: [{ label: 'Frame insertion', likelihood: .7 }, { label: 'Encoder glitch', likelihood: .2 }, { label: 'Dropped frames', likelihood: .1 }], model: M },
  { id: 'F-023', evidenceId: 'EV-0194', branch: 'audio_visual', severity: 'medium', status: 'second_review', confidence: .61, title: 'Lip-sync drifts by 140 ms', detail: 'Mouth shapes trail the audio on six words. Part of it may be a codec delay, so this stays in review.', startSec: 21, endSec: 27, region: { x: 39, y: 61, w: 22, h: 10 }, explanations: [{ label: 'Dubbed speech', likelihood: .45 }, { label: 'Codec delay', likelihood: .4 }, { label: 'Network jitter', likelihood: .15 }], model: { name: 'NX-AVS', version: '1.3.0' } },
  { id: 'F-024', evidenceId: 'EV-0194', branch: 'provenance', severity: 'medium', status: 'open', confidence: .74, title: 'Re-encoded after the capture date', detail: 'The container was written by FFmpeg three days after the camera’s own creation time.', startSec: null, endSec: null, region: null, explanations: [{ label: 'Edited and re-exported', likelihood: .55 }, { label: 'Platform transcode', likelihood: .35 }, { label: 'Archive conversion', likelihood: .1 }], model: { name: 'NX-PRV', version: '1.1.0' } },
  { id: 'F-031', evidenceId: 'EV-0195', branch: 'temporal', severity: 'medium', status: 'open', confidence: .58, title: 'Eleven seconds missing', detail: 'The lobby clock jumps from 17:55:41 to 17:55:52 between two frames.', startSec: 41, endSec: 52, region: { x: 55, y: 8, w: 18, h: 14 }, explanations: [{ label: 'Recorder gap', likelihood: .6 }, { label: 'Deleted segment', likelihood: .4 }], model: M },
  { id: 'F-041', evidenceId: 'EV-0198', branch: 'spatial', severity: 'low', status: 'open', confidence: .55, title: 'Uneven noise in the lower right', detail: 'Sensor noise in the lower right is smoother than the rest of the frame.', startSec: null, endSec: null, region: { x: 62, y: 58, w: 30, h: 32 }, explanations: [{ label: 'Local retouch', likelihood: .55 }, { label: 'Raindrop blur', likelihood: .45 }], model: M },
  { id: 'F-051', evidenceId: 'EV-0140', branch: 'provenance', severity: 'high', status: 'open', confidence: .83, title: 'Timestamps disagree by 41 minutes', detail: 'The burnt-in clock and the file creation time are 41 minutes apart.', startSec: 12, endSec: 14, region: { x: 6, y: 8, w: 26, h: 10 }, explanations: [{ label: 'Re-upload with new time', likelihood: .62 }, { label: 'Clock drift', likelihood: .38 }], model: { name: 'NX-PRV', version: '1.1.0' } },
  { id: 'F-061', evidenceId: 'EV-0149', branch: 'spatial', severity: 'high', status: 'open', confidence: .79, title: 'Repeated figures in the crowd', detail: 'Three groups of people in the left third repeat with identical poses.', startSec: 8, endSec: 31, region: { x: 4, y: 52, w: 32, h: 40 }, explanations: [{ label: 'Clone stamping', likelihood: .7 }, { label: 'Video loop', likelihood: .3 }], model: M },
];

export const decisions: Decision[] = [
  { id: 'D1', kind: 'accept_finding', severity: 'high', title: 'Blending seam along the left jaw', caseId: 'NX-10487', findingId: 'F-021', rationale: 'Spatial 0.91, agrees with the temporal break' },
  { id: 'D2', kind: 'accept_finding', severity: 'high', title: 'Repeated figures in the crowd', caseId: 'NX-10483', findingId: 'F-061', rationale: 'Spatial 0.79, no second source yet' },
  { id: 'D3', kind: 'resolve_conflict', severity: 'medium', title: 'Timestamps disagree by 41 minutes', caseId: 'NX-10486', findingId: 'F-051', rationale: 'Burnt-in clock against file creation time' },
  { id: 'D4', kind: 'approve_report', severity: 'info', title: 'Platform 6 incident, final report', caseId: 'NX-10471', rationale: 'All branches verified, signed by S. Moran' },
];

export const activity: ActivityItem[] = [
  { id: 'A1', at: '2025-01-26T14:06:00Z', text: 'Spatial branch flagged F-021', caseId: 'NX-10487', actor: 'NX-ANL', kind: 'finding' },
  { id: 'A2', at: '2025-01-26T13:41:00Z', text: 'Moved to review', caseId: 'NX-10486', actor: 'S. Moran', kind: 'status' },
  { id: 'A3', at: '2025-01-26T12:58:00Z', text: 'Original sealed', caseId: 'NX-10487', actor: 'R. Carter', kind: 'integrity' },
  { id: 'A4', at: '2025-01-26T12:02:00Z', text: 'Crowd analysis completed', caseId: 'NX-10483', actor: 'NX-ANL', kind: 'analysis' },
];

const inGraph = ['NX-10487', 'NX-10483', 'NX-10486'];
const gEv = evidence.filter(e => inGraph.includes(e.caseId));
const gFi = findings.filter(f => gEv.some(e => e.id === f.evidenceId));
export const graph: Graph = {
  nodes: [
    ...cases.filter(c => inGraph.includes(c.id)).map((c): GraphNode => ({ id: c.id, kind: 'case', label: c.name, detail: c.summary, status: c.status })),
    ...gEv.map((e): GraphNode => ({ id: e.id, kind: 'media', label: e.fileName, detail: `${e.kind === 'image' ? 'Image' : 'Video'} · ${e.source}`, refId: e.id, cluster: e.caseId, status: e.status, thumb: e.media.thumb })),
    ...gFi.map((f): GraphNode => ({ id: f.id, kind: 'finding', label: f.title, detail: `${f.detail}`, refId: f.id, cluster: gEv.find(e => e.id === f.evidenceId)!.caseId, severity: f.severity })),
    { id: 'M-ENC', kind: 'metadata', label: 'Encoder: FFmpeg', detail: 'Found on EV-0194 and EV-0149: both re-exported by FFmpeg.', severity: 'medium' },
    { id: 'M-CLK', kind: 'metadata', label: 'Clock offset +41 min', detail: 'The burnt-in clock differs from the file time on EV-0140 and EV-0195.', severity: 'medium' },
    { id: 'S-FX3', kind: 'source', label: 'Sony FX3 camera', detail: 'Camera body recorded in the original interview metadata.', status: 'verified' },
    { id: 'S-UPL', kind: 'source', label: '@newsdesk_live', detail: 'First uploader of both the interview clip and the crowd video.', severity: 'high' },
  ],
  edges: [
    ...gEv.map((e): GraphEdge => ({ from: e.caseId, to: e.id, kind: 'contains' })),
    ...gFi.map((f): GraphEdge => ({ from: f.evidenceId, to: f.id, kind: 'contains' })),
    { from: 'F-021', to: 'F-061', kind: 'pattern', label: 'Same blending kernel' }, { from: 'F-022', to: 'F-021', kind: 'pattern', label: 'Same 0.4 s window' },
    { from: 'EV-0194', to: 'M-ENC', kind: 'metadata' }, { from: 'EV-0149', to: 'M-ENC', kind: 'metadata' },
    { from: 'EV-0140', to: 'M-CLK', kind: 'timestamp' }, { from: 'EV-0195', to: 'M-CLK', kind: 'timestamp' }, { from: 'F-051', to: 'F-031', kind: 'timestamp', label: 'Both clocks off' },
    { from: 'EV-0194', to: 'S-FX3', kind: 'derived' }, { from: 'EV-0196', to: 'EV-0197', kind: 'derived', label: 'Same street, 8 min apart' },
    { from: 'S-UPL', to: 'EV-0194', kind: 'derived' }, { from: 'S-UPL', to: 'EV-0149', kind: 'derived' },
  ],
};

export const assessments: Record<string, Assessment> = {
  'NX-10487': { caseId: 'NX-10487', outcomes: [{ label: 'Localized manipulation', low: 38, high: 56 }, { label: 'Authentic', low: 20, high: 35 }, { label: 'Inconclusive', low: 18, high: 34 }], note: 'A missing branch counts as missing evidence, never as proof.' },
};

export const audit: AuditEvent[] = [
  [418, '2025-01-26T16:37:21Z', 'evidence_access', 'R. Vale', 'Viewed EV-0194', true], [417, '2025-01-26T16:34:02Z', 'analysis', 'S. Moran', 'Analysis run completed on NX-10487', true],
  [416, '2025-01-26T15:58:40Z', 'model_change', 'R. Vale', 'NX-ANL 2.4.1 deployed', true], [415, '2025-01-26T15:12:09Z', 'access_control', 'S. Moran', 'L. Chen given read access', true],
  [414, '2025-01-25T18:40:55Z', 'export', 'R. Vale', 'Case package NX-10471 exported', true], [413, '2025-01-25T17:22:31Z', 'retention', 'D. Arden', 'Retention schedule RP-03 applied', true],
  [412, '2025-01-25T11:05:14Z', 'access_control', 'S. Moran', 'Contractor access revoked', false], [411, '2025-01-24T09:47:03Z', 'evidence_access', 'L. Chen', 'Viewed EV-0149', true],
].map(([seq, at, kind, actor, text, verified]) => ({ seq, at, kind, actor, text, verified, signature: `${String(seq).slice(1)}fa27ec…b1d4` }) as AuditEvent);

export const models: ModelInfo[] = [
  { name: 'NX-ANL', version: '2.4.1', status: 'deployed' }, { name: 'NX-AVS', version: '1.3.0', status: 'deployed' },
  { name: 'NX-PRV', version: '1.1.0', status: 'deployed' }, { name: 'NX-CLS', version: '1.2.2', status: 'approved' },
];
