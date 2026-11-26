# Module Connectivity

The investigation modules and how they connect. Two flowcharts were supplied; both are reproduced below
exactly as given (transcribed from the specification messages of 26 November 2026). Do not edit the Mermaid
blocks: they are the canonical specifications. Interpretation and decisions are in the sections after them.

| Flowchart | Authority | Use |
|---|---|---|
| **A1** — latest module connectivity | **Highest.** Defines exact module relationships and T-MIR's coordination boundary | Source of the dependency registry (`Backend/App/Orchestration/TMir/DependencyRegistry.py`) |
| **A2** — grouped module flowchart | Second. Useful visualization of the five groups | Group names and visual structure |

The registry test (`Tests/Unit/Backend/test_dependency_registry.py`) parses the A1 block in this file and fails
if the registry's edges differ from it by a single arrow.

## A1 — Latest canonical module connectivity

```mermaid
flowchart TD
    CM["01 NEX-CM<br/>Case Management"]
    CAP["02 NEX-CAP<br/>Evidence Acquisition"]
    EVD["03 NEX-EVD<br/>Evidence Preservation"]

    MET["04 NEX-MET<br/>Metadata Intelligence"]
    IMG["05 NEX-IMG<br/>Image Forensics"]
    VID["06 NEX-VID<br/>Video Forensics"]
    AUD["07 NEX-AUD<br/>Audio Forensics"]
    PRV["08 NEX-PRV<br/>Provenance Intelligence"]

    SRC["09 NEX-SRC<br/>Source Intelligence"]
    FPM["10 NEX-FPM<br/>Fingerprint & Similarity"]
    MOC["11 NEX-MOC<br/>Media Lineage"]

    ALN["12 NEX-ALN<br/>Temporal Alignment"]
    TRN["13 NEX-TRN<br/>Transformation Analysis"]
    CMC["14 NEX-CMC<br/>Cross-Modal Correlation"]

    EGC["15 NEX-EGC<br/>Evidence Graph Construction"]
    REC["16 NEX-REC<br/>Timeline & Reconstruction"]
    INV["17 NEX-INV<br/>Review & Decision"]
    RPT["18 NEX-RPT<br/>Reporting"]

    CM --> CAP --> EVD

    EVD --> MET
    EVD --> IMG
    EVD --> VID
    EVD --> AUD
    EVD --> PRV

    MET --> FPM
    IMG --> FPM
    VID --> FPM
    AUD --> FPM
    SRC --> FPM

    FPM --> MOC
    SRC --> MOC

    MOC --> ALN
    IMG --> ALN
    VID --> ALN

    ALN --> TRN
    MOC --> TRN

    IMG --> CMC
    VID --> CMC
    AUD --> CMC
    PRV --> CMC
    TRN --> CMC

    SRC --> EGC
    MOC --> EGC
    TRN --> EGC
    CMC --> EGC

    EGC --> REC --> INV --> RPT

    TMIR["T-MIR ORCHESTRATION"] -. "coordinates execution" .-> MET
    TMIR -.-> IMG
    TMIR -.-> VID
    TMIR -.-> AUD
    TMIR -.-> PRV
    TMIR -.-> FPM
    TMIR -.-> MOC
    TMIR -.-> ALN
    TMIR -.-> TRN
    TMIR -.-> CMC
    TMIR -.-> EGC
    TMIR -.-> REC
```

## A2 — Grouped module flowchart

```mermaid
flowchart TB

    START(["NEXTRON INVESTIGATION"])

    subgraph FOUNDATION["INVESTIGATION FOUNDATION"]
        CM["NEX-CM<br/>Case Management"]
        CAP["NEX-CAP<br/>Evidence Acquisition"]
        EVD["NEX-EVD<br/>Evidence Preservation"]
    end

    subgraph MEDIA["MEDIA INTELLIGENCE"]
        MET["NEX-MET<br/>Metadata Intelligence"]
        IMG["NEX-IMG<br/>Image Forensics"]
        VID["NEX-VID<br/>Video Forensics"]
        AUD["NEX-AUD<br/>Audio Forensics"]
        PRV["NEX-PRV<br/>Provenance Intelligence"]
    end

    subgraph ORIGIN["ORIGIN & CIRCULATION INTELLIGENCE"]
        SRC["NEX-SRC<br/>Source Intelligence"]
        FPM["NEX-FPM<br/>Fingerprint & Similarity"]
        MOC["NEX-MOC<br/>Media Lineage"]
    end

    subgraph CORRELATION["CORRELATION INTELLIGENCE"]
        ALN["NEX-ALN<br/>Temporal Alignment"]
        TRN["NEX-TRN<br/>Transformation Analysis"]
        CMC["NEX-CMC<br/>Cross-Modal Correlation"]
    end

    subgraph INVESTIGATION["INVESTIGATION INTELLIGENCE"]
        EGC["NEX-EGC<br/>Evidence Graph Construction"]
        REC["NEX-REC<br/>Timeline & Reconstruction"]
        INV["NEX-INV<br/>Review & Decision"]
        RPT["NEX-RPT<br/>Reporting"]
    end

    TMIR(("NEX-TMIR<br/>CENTRAL INTELLIGENCE<br/>ORCHESTRATION CORE"))

    START --> CM
    CM --> CAP
    CAP --> EVD

    EVD --> MET
    EVD --> IMG
    EVD --> VID
    EVD --> AUD
    EVD --> PRV

    MET --> FPM
    IMG --> FPM
    VID --> FPM
    AUD --> FPM
    SRC --> FPM

    FPM --> MOC

    IMG --> ALN
    VID --> ALN
    MOC --> ALN

    ALN --> TRN
    MOC --> TRN

    IMG --> CMC
    VID --> CMC
    AUD --> CMC
    PRV --> CMC
    TRN --> CMC

    SRC --> EGC
    MOC --> EGC
    TRN --> EGC
    CMC --> EGC

    EGC --> REC
    REC --> INV
    INV --> RPT

    TMIR -.-> CM
    TMIR -.-> CAP
    TMIR -.-> EVD
    TMIR -.-> MET
    TMIR -.-> IMG
    TMIR -.-> VID
    TMIR -.-> AUD
    TMIR -.-> PRV
    TMIR -.-> SRC
    TMIR -.-> FPM
    TMIR -.-> MOC
    TMIR -.-> ALN
    TMIR -.-> TRN
    TMIR -.-> CMC
    TMIR -.-> EGC
    TMIR -.-> REC
    TMIR -.-> INV
    TMIR -.-> RPT

    RPT --> END(["INVESTIGATION REPORT"])
```

## How the two differ, and what is implemented

| Difference | A1 | A2 | Implemented (decision) |
|---|---|---|---|
| `SRC --> MOC` | present | absent | **Present** — A1 is the higher authority (conflict C-2) |
| T-MIR dotted edges | 12 modules (MET … REC) | all 18 | **T-MIR executes the 12**; CM, CAP, EVD, SRC, INV, RPT are owned by domain services and observed through events (C-1 / D-2) |
| START / END nodes | absent | present | Entry and output labels only; not modules |

Every other solid edge is identical in both: 31 module-to-module edges in A1, 30 in A2.

## Reading the arrows

- A **solid arrow** is data flow: the downstream module consumes the upstream module's persisted results.
  It is not automatically a blocking dependency. Each edge is typed in the registry:
  - `REQUIRED` — the downstream cannot run without a completed upstream result.
  - `CONDITIONAL` — required only when the upstream applies to the same evidence or pair (e.g. IMG → FPM only for images).
  - `OPTIONAL` — used when present; its absence or failure becomes a recorded limitation.
- A **dotted arrow** is control: T-MIR schedules and coordinates that module. Modules never call each other.
- Modules may read **foundation records** (cases, evidence, artifacts) by reference without an edge (decision D-6).

The complete edge table, with types and the reason for each, is generated from the registry in
[Orchestration.md](Orchestration.md#dependency-registry).

## Edges in neither flowchart (documented, not added)

| Missing edge | Why it matters | Resolution |
|---|---|---|
| `AUD --> ALN` | The archive gives NEX-ALN audio alignment | ALN reaches audio through MOC's version pairs and FPM's audio fingerprints (C-4) |
| `MET --> CMC` | The archive lists metadata as a correlation input | Metadata reaches correlation through FPM/MOC; MET reports its own inconsistencies (C-5) |
| `CM --> SRC`, an entry for SRC | SRC has no upstream in either flowchart | Sources enter by an investigator-supplied URL; a source-resolution job (D-13) |
| `VID --> IMG`, `VID --> AUD` | The archive had VID hand frames to IMG and audio to AUD | IMG analyses images; VID its own frames; AUD extracts the audio track itself (C-6) |
