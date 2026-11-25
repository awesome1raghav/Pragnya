# NEXTRON backend API

The workspace (`/workspace`) talks to the backend through one typed interface, `NextronApi`, defined in
[`app/workspace/api/contract.ts`](../app/workspace/api/contract.ts). That file is the source of truth: every
shape below is copied from it. When this document and that file disagree, the file wins.

## Switching the frontend to your server

```bash
# .env.local
NEXT_PUBLIC_NEXTRON_API=https://api.nextron.example
```

Unset, the app runs on an in-memory mock (`app/workspace/api/mock.ts`) with demo data, so frontend work never
waits on the backend. Set, every call goes to your server through `app/workspace/api/http.ts`. No component
changes are needed either way.

- **Auth.** If `localStorage['nx-token']` is set, every request carries `Authorization: Bearer <token>`.
- **CORS.** Allow the frontend origin, the `Authorization` and `Content-Type` headers, and `GET, POST, PATCH`.
- **Errors.** Any non-2xx is shown to the user. Send a short plain-text or JSON message body; the status code decides nothing else.

## Conventions

| Thing | Rule | Example |
|---|---|---|
| IDs | Opaque strings, stable forever | `"EV-0194"` |
| Times | ISO-8601, UTC | `"2025-01-21T18:02:14Z"` |
| Offsets into media | Seconds, as numbers | `23.7` |
| Confidence, likelihood | 0 to 1 | `0.91` |
| Readiness, outcome ranges | 0 to 100 | `84` |
| Regions | Percent of the still image, origin top-left | `{ "x": 30, "y": 54, "w": 22, "h": 18 }` |
| Enums | snake_case; the UI owns all labels and colours | `"in_review"` |
| Image URLs | Directly loadable by the browser (signed URLs are fine) | `"https://cdn…/EV-0194/still.webp"` |

## Routes

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/cases` | | `Case[]` |
| GET | `/evidence?caseId=` | | `Evidence[]` (all when `caseId` is absent) |
| POST | `/evidence` | multipart: `file`, `caseId`, `sha256` | `Evidence` |
| GET | `/findings?caseId=&evidenceId=` | | `Finding[]` |
| PATCH | `/findings/:id` | `{ "status": FindingStatus }` | `Finding` |
| GET | `/graph` | | `Graph` |
| GET | `/cases/:id/assessment` | | `Assessment` |
| GET | `/decisions` | | `Decision[]` |
| POST | `/decisions/:id` | `{ "action": DecisionAction }` | `204` |
| GET | `/activity` | | `ActivityItem[]` |
| GET | `/audit` | | `AuditEvent[]` |
| GET | `/models` | | `ModelInfo[]` |
| POST | `/analysis` | `{ "evidenceId": "EV-0194" }` | `AnalysisJob` |
| GET | `/analysis/:id` | | `AnalysisJob` |

### Upload: `POST /evidence`

The browser computes SHA-256 over the original before uploading and sends it as `sha256`.
**Recompute it on the server and reject the upload (409) if it differs.** That check is the chain-of-custody guarantee.
Then store the original read-only, generate `media.still` and `media.thumb`, and return the new `Evidence`.

### Analysis: `POST /analysis`, then poll `GET /analysis/:id`

The UI polls every 250 ms while `state` is `queued` or `running`. It shows `stages` exactly as you send them, so name
them for people (`"Spatial, temporal and audio-visual branches"`). When `state` becomes `done`, include `findings`.
The UI also reloads `/findings` afterwards. On `failed`, put a readable reason in `error`.

```json
{
  "id": "JOB-lq3k9",
  "evidenceId": "EV-0194",
  "state": "running",
  "progress": 0.55,
  "stages": [
    { "key": "verify", "label": "Verify sealed hash", "state": "done" },
    { "key": "sample", "label": "Sample frames and track faces", "state": "done" },
    { "key": "branches", "label": "Spatial, temporal and audio-visual branches", "state": "running" },
    { "key": "fuse", "label": "Fuse evidence", "state": "waiting" }
  ]
}
```

### Decisions: `POST /decisions/:id`

`action` is one of `accept`, `resolve`, `approve`, `escalate`, `dismiss`. Remove the decision from `GET /decisions`
afterwards. `accept` and `resolve` should also set the linked finding's status to `accepted`. Write an audit event for every action.

## Shapes, with examples

### Case

```json
{
  "id": "NX-10487",
  "name": "Corvane interview clip",
  "summary": "Suspected face swap in a recorded broadcast interview",
  "status": "flagged",
  "priority": 96,
  "reason": "Two high-severity findings are waiting for your decision.",
  "analyst": "R. Carter",
  "updatedAt": "2025-01-26T14:06:00Z",
  "legalHold": true,
  "cover": { "still": "…/interview-1280.webp", "thumb": "…/interview-480.webp", "width": 900, "height": 1125, "focus": { "x": 0.5, "y": 0.3 } },
  "readiness": { "spatial": 92, "temporal": 78, "audio_visual": 61, "provenance": 84 }
}
```

- `status` is one of `flagged | in_review | active | on_hold | verified`.
- The command centre focuses the case with the highest `priority` and shows its `reason` verbatim. Keep it to one sentence.
- `readiness[branch] = null` means that branch does not apply (for example, footage with no audio).

### Evidence

```json
{
  "id": "EV-0194", "caseId": "NX-10487", "fileName": "interview_clip.mp4", "kind": "video", "status": "flagged",
  "durationSec": 48, "source": "Broadcast upload", "capturedAt": "2025-01-21T18:02:14Z",
  "sha256": "9f4e2a6b8d9c7d0f6a3b1e9a2b7d4e5f8c9d0a1b", "sizeBytes": 883532595,
  "width": 1920, "height": 1080, "codec": "H.264 / AAC",
  "media": { "still": "…", "thumb": "…", "overlay": "…", "width": 900, "height": 1125 },
  "metadata": [
    { "key": "Encoder", "value": "Lavf 60.3.100 (FFmpeg)", "conflict": true, "note": "Camera files are written by the camera, not by FFmpeg" }
  ]
}
```

- `media.still` and `media.overlay` must have the same pixel size. The UI lays the overlay over the still to compare them.
- `metadata[].conflict = true` turns the row red and counts it in "metadata conflicts" on the command centre.

### Finding: see [ML_OUTPUT_SPEC.md](ML_OUTPUT_SPEC.md)

### Graph

```json
{
  "nodes": [
    { "id": "NX-10487", "kind": "case", "label": "Corvane interview clip", "detail": "…", "status": "flagged" },
    { "id": "EV-0194", "kind": "media", "label": "interview_clip.mp4", "detail": "Video · Broadcast upload", "refId": "EV-0194", "cluster": "NX-10487", "status": "flagged", "thumb": "…" },
    { "id": "F-021", "kind": "finding", "label": "Blending seam along the left jaw", "detail": "…", "refId": "F-021", "cluster": "NX-10487", "severity": "high" },
    { "id": "M-ENC", "kind": "metadata", "label": "Encoder: FFmpeg", "detail": "…", "severity": "medium" }
  ],
  "edges": [
    { "from": "NX-10487", "to": "EV-0194", "kind": "contains" },
    { "from": "F-021", "to": "F-061", "kind": "pattern", "label": "Same blending kernel" }
  ]
}
```

- `kind` (node) is one of `case | media | finding | metadata | source`.
- `kind` (edge) is one of `contains | pattern | timestamp | metadata | derived`.
- `cluster` groups a node under a case, so the UI can collapse it.
- `refId` points at the `Evidence` or `Finding` the node stands for; it is used to open that item.

### Assessment, Decision, ActivityItem, AuditEvent, ModelInfo

See `contract.ts`. Each one is a flat object with the fields listed there and no nesting beyond what is shown.

## Testing against the contract

The example payloads your responses should match are in
[`app/workspace/api/fixtures.ts`](../app/workspace/api/fixtures.ts): the exact objects the mock returns.
To check your server, point `NEXT_PUBLIC_NEXTRON_API` at it and walk through every view. Any field your server
leaves out shows up as an empty or broken element.
