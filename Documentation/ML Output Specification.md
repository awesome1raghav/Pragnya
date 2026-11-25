# What the ML pipeline must produce

The UI can show anything your models find, as long as each result arrives as a **`Finding`** plus, for each piece of
evidence, an **overlay image**. This page covers what each field means on screen, so you can choose the values on
purpose. The exact type is in [`Frontend/src/api/contract.ts`](../Frontend/src/api/contract.ts).

## 1. One `Finding` per thing an investigator should look at

```json
{
  "id": "F-021",
  "evidenceId": "EV-0194",
  "branch": "spatial",
  "severity": "high",
  "status": "open",
  "title": "Blending seam along the left jaw",
  "detail": "Texture and lighting along the jawline differ from the cheek above it, the typical edge of a swapped face.",
  "confidence": 0.91,
  "startSec": 22.4,
  "endSec": 26.1,
  "region": { "x": 30, "y": 54, "w": 22, "h": 18 },
  "explanations": [
    { "label": "Face swap", "likelihood": 0.74 },
    { "label": "Beauty filter", "likelihood": 0.18 },
    { "label": "Compression edge", "likelihood": 0.08 }
  ],
  "model": { "name": "NX-ANL", "version": "2.4.1" }
}
```

| Field | What the UI does with it | Rules |
|---|---|---|
| `branch` | Groups the finding and colours its timeline track | `spatial` (pixels in a frame), `temporal` (between frames), `audio_visual` (sound against picture), `provenance` (file, metadata, source) |
| `severity` | Red for `high`, blue for `medium`, grey for `low`; `high` lands in the decision queue | Decide from calibrated confidence **and** impact, not confidence alone |
| `title` | The list label, the region label and the report heading | Plain words, at most 6–8 of them, no model jargon. "Frames 712 to 724 replaced", not "TCN anomaly score > τ" |
| `detail` | Inspector text and the report paragraph | One or two sentences an investigator could read aloud in court |
| `confidence` | Shown to two decimals; sorts the focal region | **Calibrated** probability (0..1). Temperature-scale or isotonic-fit your scores first |
| `startSec`, `endSec` | Red band on the scrubber, timeline marker, the playhead jumps here | Seconds from the start of the file. `null` for stills or whole-file findings (most provenance findings) |
| `region` | The box drawn on the frame, the zoomed crop in the inspector | **Percent of the still image**, top-left origin: `x = box_px_x / still_width * 100`. `null` when there is nothing to point at |
| `explanations` | "Most likely cause" chips with percentages | 2–4 competing causes, likelihoods summing to about 1, most likely first. Always include a benign cause when one is plausible |
| `model` | Inspector line and audit trail | The exact model name and version that produced it |

### The region coordinate rule, worked through

The UI shows each piece of evidence through its `media.still` (about 1280 px wide), at whatever size fits the
screen. A region in percent stays on the same pixels at every size and in every crop. The UI does the cover/crop maths itself.

```python
# bbox from your detector, in pixels of the frame you analysed (W x H)
x0, y0, x1, y1 = 576, 583, 998, 777
W, H = 1920, 1080
region = {"x": x0 / W * 100, "y": y0 / H * 100, "w": (x1 - x0) / W * 100, "h": (y1 - y0) / H * 100}
```

If the still was cropped from the analysed frame, convert into the **still's** pixel space first.

## 2. One overlay image per piece of evidence

`Evidence.media.overlay` is the image behind the **Compare** slider, the **Frames → Error level** layer and the loupe.

- **Size:** exactly the same width and height as `media.still`.
- **Content:** a visual explanation of *where* the evidence is suspicious: an error-level map, a heat map from a
  spatial model, a noise-residual map. Dark means "nothing here" and bright means "look here".
- **Palette:** keep the UI colours so it reads at a glance. Steel blue `#7FA6BF` for low, amber `#E9A23B` for medium,
  red `#F0604D` for high, over a near-black version of the frame.
- **Format:** WebP or JPEG, quality around 80, about 1280 px wide.

`public/images/evidence/*-ela.webp` are examples of what the UI expects.

## 3. Per-case numbers

| Field | Where | Meaning |
|---|---|---|
| `Case.readiness[branch]` | Command centre meter | Share of that branch's checks completed for the case, 0–100. `null` if the branch does not apply |
| `Assessment.outcomes` | Graph view, "Fused assessment" | Plausible range for each outcome after fusing the branches, as `{ label, low, high }` in percent. Put the leading outcome first |
| `Assessment.note` | Under the ranges | One sentence of caveats. Say plainly when a branch is missing |

## 4. Graph relationships the models can supply

Add edges to `/graph` when your pipeline finds them:

- `pattern`: two findings share a manipulation signature (same blending kernel, same generator fingerprint).
- `timestamp`: two items disagree about time (burnt-in clock against file time, two uploads).
- `metadata`: items share a metadata trait (same encoder, same editing software).
- `derived`: items come from the same source, or one is a copy of another (perceptual-hash match).

Each edge's `label` is shown in the detail panel. Write it in plain words: "Same blending kernel".

## 5. Checklist before you hand results to the backend

- [ ] Confidence is calibrated, not a raw logit or softmax score.
- [ ] Every `region` is in percent of the still, not pixels.
- [ ] `startSec` and `endSec` are in seconds, not frame numbers.
- [ ] Titles are 6–8 plain words; details are 1–2 sentences.
- [ ] Each finding lists at least one benign explanation when one is plausible.
- [ ] Each overlay matches its still's pixel size exactly.
- [ ] The model name and version are on every finding.
