# NEXTRON workspace — visual UI/UX audit

**Reviewed:** 26 November 2026  
**Site:** `http://localhost:3000`  
**Scope:** the workspace only. The landing page was excluded at the user's request.  
**Deliverable:** design findings and proposed fixes. No product UI or route code was changed for this audit.

## Verdict

NEXTRON already has a coherent forensic identity: near-black surfaces, restrained amber actions, distinct evidence imagery, a genuinely useful three-panel viewer, an interactive graph, and an unusually convincing report preview. The gap between this and a standout design is **composition and control hierarchy across states**. The best parts are concentrated in the viewer and report; tablet and phone layouts often collapse into cramped controls, long empty canvases, or controls that appear only after too much scrolling.

The goal should be **an evidence-led investigation instrument**. Make the selected evidence, its anomaly, and the next decision unmistakable. Use the large visual moments for evidence itself; let controls recede until needed. Keep the interface rigorous and fast. More glow, panels, motion, and badges would make it less distinctive.

### Fix first

1. Repair the **768 px header and breadcrumbs**; they visibly overlap or wrap inside fixed-height chrome.
2. Recompose the **phone graph**; the assessment bar covers Relationships, the legend is hidden by CSS, and nodes are either clipped or too small after fitting.
3. Redesign the **phone investigation toolbar and timeline**; important controls are offscreen and the timeline occupies a tall canvas with little useful content.
4. Put **report editing controls before or alongside the phone preview**; they currently begin about 2,700 px down the page.
5. Reduce the **command centre portrait's dominance** so the decision that needs attention is visible earlier, especially on phones.

## What was inspected

The running site was inspected at **390, 768, 1024, and 1440 px**. I opened all six workspace views through the navigation: Command centre, Investigation, Evidence graph, Scan evidence, Report studio, and Governance. I inspected click states for the decision menu, case expansion, command palette, Viewer/Frames/Timeline/Metadata tabs, Compare, finding inspector, graph legend/outcome/node detail, sample intake, report section selection and finding inclusion, governance filters, and mobile evidence/findings panels. I also measured visible control dimensions and checked document-width overflow at these widths.

This is a **visual and interaction-design audit**, not a backend or ML audit. I did not submit approval, accept/reject findings, or seal/upload files. Repeated controls of the same type were assessed as a group. Desktop and mobile screenshots are in `../.playwright-cli/` (for example, [Command centre](../.playwright-cli/design-desktop-command-centre.png), [Investigation](../.playwright-cli/design-desktop-investigation.png), [Graph](../.playwright-cli/design-mobile-evidence-graph.png), [Report](../.playwright-cli/design-mobile-report-studio.png)). The browser's Next.js development overlay was hidden only in the audit browser because an unrelated compile issue obscured controls; it is not part of the product design assessment.

The local site was being edited and hot-reloaded during inspection. The screenshots and recommendations describe the observed states on this date; recheck the affected views once the current edits settle.

**Observed strength:** no document-wide horizontal overflow was found in the tested widths. That does **not** mean every control is visible or reachable; several are clipped inside local scrollers or covered by other elements.

## Global design findings

| Priority | Element / observed state | Design cost | Specific fix | Acceptance criterion |
|---|---|---|---|---|
| **P0** | Top bar at **768 px**: “Search or run a command” and “Ctrl K” wrap inside a 36 px control; Investigation breadcrumbs visually run together. [Header](../.playwright-cli/design-768-investigation.png) | Navigation looks broken at a common tablet width and loses readable hierarchy. | Switch to the compact header before space becomes insufficient, around 900–960 px; show a search icon and a concise current location. Preserve full breadcrumb in a secondary disclosure or breadcrumb overflow menu. | No text wraps or collides at 760–1024 px; current case and tool remain identifiable. |
| **P1** | Desktop icon rail: six unlabelled icons depend on hover tooltips. [Rail](../.playwright-cli/design-desktop-command-centre.png) | Expert users may learn it, but first-time users must guess destinations. | Use a labelled rail at comfortable desktop widths, with the existing collapse option. Keep icon-only mode as a user choice. | Each destination is understandable without hover, tooltip, or memorized shortcut. |
| **P1** | Control sizes vary: menu buttons are **30×30 px**, graph zoom/fit buttons **28 px high**, tool tabs **28 px high**, and mobile panel buttons **36×36 px**. | Precision controls feel cramped and are harder to use on touch. | Establish 40–44 px mobile hit areas as a design target, with compact visual glyphs inside; preserve 32–36 px visible density on desktop where appropriate. | Every phone control has a comfortable target without increasing visual clutter. |
| **P1** | Many labels, IDs, timestamps, and helper lines use 11–13 px muted text. | The interface feels dense while actual reading is slow; status words become harder to distinguish. | Use 14 px for operational labels, 13 px for secondary metadata, and monospace only for hashes, IDs, timestamps, and measurements. Reserve the faintest tone for nonessential marks. | Core task labels remain readable at normal scale and 200% zoom. |
| **P2** | Near-black panels have similar value and radius across the command, intake, governance, and report controls. | The page reads as a series of boxes, even when information importance differs. | Use open space and a stronger type hierarchy for secondary information; reserve raised panels for actionable regions. | An investigator can identify the primary task before reading every card header. |
| **P2** | Hover tooltip remained over headings in audit screenshots immediately after clicking the rail. | Tooltip positioning can visually clash with content at the top-left. | Anchor tooltip beside the icon within the rail layer, and dismiss it immediately on navigation/selection. | The destination heading is never obscured by the previous item's tooltip. |

The actual CSS design tokens are warm black and amber in [workspace.module.css](../app/workspace/workspace.module.css). The cached [`.21st/design.json`](../.21st/design.json) still describes navy and teal, and nine surfaces rather than the current six. Update that design reference before using generated design assistance; otherwise future work may drift away from this identity. The automated 21st review found **0 errors, 0 warnings, and 101 informational color-token suggestions** in the current workspace files. Those suggestions are not 101 visual defects.

The 40–44 px phone target above is a **comfort recommendation**, not a claimed WCAG pass threshold. [WCAG 2.2's target-size criterion](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum) specifies 24×24 CSS px with exceptions. [Awwwards' published Mobile Excellence guidelines](https://www.awwwards.com/mobile-excellence-guidelines.pdf) also call out visible key actions, legible text, appropriately sized tap targets, and content that fits the viewport. This report applies those principles to the observed NEXTRON screens; it does not claim an official award score.

## Page-by-page control audit

### 1. Command centre

**Keep:** the asymmetric focus case plus decision queue, distinct case thumbnails, and the choice to inspect before deciding. The [desktop view](../.playwright-cli/design-desktop-command-centre.png) has a clear overall grid.

| Priority | Control / state | Observed visual issue | Design fix |
|---|---|---|---|
| **P1** | Priority case | The portrait fills roughly half of the large lead tile. On [mobile](../.playwright-cli/design-mobile-command-centre.png), the first decision queue starts around **y=960 px**, after the image, readiness bars, two actions, and “Up next.” | Reduce portrait height on mobile and bring **Next decision / Inspect** into the first screen. Keep a medium still or crop as context, not the entire visual argument. |
| **P1** | Three summary chips | Mobile chips scroll sideways with the third initially hidden and no visual cue that the row continues. | Show two concise metrics and a clear “More status” affordance, or use a compact two-row summary. Do not rely on invisible horizontal overflow. |
| **P2** | Readiness percentages | Four equally weighted meters imply precision yet obscure what is missing; on tablet “Audio-visual” wraps into two lines. | Lead with the branch needing review and a short status phrase. Put exact percentages in an expandable breakdown. Keep labels on one line at 768 px. |
| **P2** | Decision row / “More” menu | The menu opens over subsequent decision rows. [Clicked state](../.playwright-cli/state-decision-menu.png) is legible but crowded; “Accept without inspecting” receives similar visual weight to safer actions. | Use a compact contextual menu with clearer group spacing and muted treatment for exceptional actions. Do not let the menu visually merge with the next row. |
| **P2** | Case rows / expansion | Case rows are clean, but the chevron and status become very small on mobile. | Increase the touch region for the whole row and show a clear expanded boundary; keep status visible at narrow widths. |
| **P2** | Activity | The “Signed” label and event log form a second dashboard panel, competing with decisions. | Compress to recent activity until requested; let the decision queue remain dominant. |

### 2. Investigation workspace

**Keep:** the evidence / canvas / findings structure on wide screens. The frame comparison and selected finding inspection are the most credible product moments. [Viewer](../.playwright-cli/design-desktop-investigation.png) and [finding detail](../.playwright-cli/state-finding-inspector.png).

| Priority | Control / state | Observed visual issue | Design fix |
|---|---|---|---|
| **P0** | Phone tool strip | Viewer, Frames, Timeline, Metadata, Compare, Run analysis, and panel toggles occupy one horizontally scrolling row. In the initial [phone viewer](../.playwright-cli/design-mobile-investigation.png), Compare, Run analysis, and the findings toggle are offscreen. Selecting Timeline scrolls the strip so earlier tools vanish. | Separate **mode selection** from **actions**. Use a fixed four-mode selector or a clear overflow menu; place Run analysis and panel access in a stable secondary row. A user should see the current mode and reach all main actions without guessing to swipe. |
| **P1** | Phone context | The mobile header says only “Viewer” or “Timeline.” Once side panels are hidden, the filename and case disappear from the visible frame. | Add one-line case/file context above the canvas with truncation only after the identifying portion. |
| **P1** | Timeline | Four narrow traces occupy the top ~220 px, followed by a large empty canvas until the bottom scrubber. [Desktop](../.playwright-cli/state-investigation-timeline.png), [mobile](../.playwright-cli/state-mobile-timeline.png). Mobile axis time labels run into each other. | Give the timeline a dedicated height based on content. Place selected intervals, frame preview, and finding explanation next to or below the traces. Use fewer mobile tick labels and a movable time ruler. |
| **P1** | Viewer vertical placement on phone | The image floats between substantial empty bands, while the scrubber is pinned at the bottom. | Set the canvas height from image aspect ratio and available controls, then use the remaining space for a selected-finding strip or compact context. |
| **P1** | Findings on phone | Opening findings replaces most of the canvas with a full-height side sheet. [Clicked state](../.playwright-cli/state-mobile-findings-panel.png) shows a large empty lower region after four rows. | Make it a bottom sheet with snap heights or a compact list that expands only for the chosen finding. Keep a visible reference to the affected frame. |
| **P2** | Frames / Error level / Loupe | The mode called “Frames” primarily presents a single error-level image with a tiny range slider. [Clicked state](../.playwright-cli/state-investigation-frames.png). | Rename or reorganize the mode so frame navigation and image examination have distinct, visible roles. Put the strength control near the image legend. |
| **P2** | Compare button | Its persistent state is shown mainly through a gold icon and slight text change. | Give Compare a stronger selected treatment and show “Original / Error level” labels where the split is actually manipulated. |
| **P2** | Metadata | Metadata occupies only the upper part of a full-height canvas; conflict rows are useful but disconnected from the corresponding finding. [Clicked state](../.playwright-cli/state-investigation-metadata.png). | Group provenance, technical media, and conflicts; give conflicts a direct visual route to related evidence. Avoid forcing a full-screen empty table surface. |

### 3. Evidence graph

**Keep:** the relationship types, selected-node inspector, and Fit control. The graph is distinctive enough to become a signature feature if its visual density is controlled.

| Priority | Control / state | Observed visual issue | Design fix |
|---|---|---|---|
| **P0** | Mobile bottom controls | The **38–56% assessment bar overlays the Relationships button**. A normal browser click on Relationships was intercepted by the assessment bar. [Mobile graph](../.playwright-cli/design-mobile-evidence-graph.png). | Give Relationships and assessment separate, nonoverlapping slots; never stretch a collapsed assessment control over another action. |
| **P0** | Relationships popover on phone | The button can be programmatically activated, but the popover is explicitly `display:none` under 760 px, so it reveals nothing. [CSS](../app/workspace/workspace.module.css). | Render relationship filters as a bottom sheet or compact legend list on mobile. A visible control must always reveal a visible state. |
| **P1** | Initial mobile framing | At one moment peripheral nodes are cut off; after Fit the entire network becomes too tiny to read. [Initial](../.playwright-cli/design-mobile-evidence-graph.png), [fitted](../.playwright-cli/state-mobile-graph-legend.png). | Center the **active case cluster**, not the whole network. Show adjacent nodes at readable scale; provide a list/search route to distant nodes. |
| **P1** | Graph labels | Several labels overlap edges or each other at 768–1024 px, and peripheral nodes are clipped by the canvas. [768 px](../.playwright-cli/design-768-evidence-graph.png). | Use collision-aware labels or show names on selection/focus; add an overview/minimap or edge affordance for offscreen groups. |
| **P1** | Desktop legend popover | Relationship names wrap and overlap inside a narrow panel. [Clicked state](../.playwright-cli/state-graph-legend.png). | Give each relationship one line and a predictable 220–260 px popover width; separate line sample, label, and active state. |
| **P2** | Selected-node state | Opening node details narrows/dims the graph and moves the assessment panel into the remaining canvas. [Clicked state](../.playwright-cli/state-graph-node.png). | Reserve a stable inspector width on desktop; keep auxiliary assessment in an inspector tab or corner that does not cover relationships. |
| **P2** | Zoom toolbar | Four compact icons and a search box have equal visual weight. | Lead with search and Fit; group zoom in a quieter control. On phone, expose only Fit and search until the canvas is touched. |

### 4. Scan evidence

**Keep:** the drop area, authentic local-processing stages, resulting hash, and contact sheet. The [sample state](../.playwright-cli/state-intake-sample.png) is more convincing than a generic upload spinner.

| Priority | Control / state | Observed visual issue | Design fix |
|---|---|---|---|
| **P1** | Initial scan view | The processing card lists five inactive steps before a file is chosen, visually implying the work has begun. On phone it pushes the case selector and main action far down. [Mobile](../.playwright-cli/design-mobile-scan-evidence.png). | Start with one clear upload task and a short “What happens next” line. Reveal the detailed stage list after selection. |
| **P2** | “Use a sample still” | The most approachable first-run path is visually small and buried in the bottom of a large drop zone. | Present sample as an explicit secondary route directly below “Choose file,” with clear example labeling. |
| **P2** | Post-sample contact sheet | Six tiny crops repeat in a shallow strip. | Make one selected crop large with the remaining frames as selectable thumbnails; show the selected timestamp or crop label. |
| **P2** | Disabled seal action | Disabled amber retains the size and position of the main CTA but looks like a faded primary button. | Use a neutral disabled surface before a file is ready; switch to amber only when the next action is available. |

### 5. Report studio

**Keep:** the archival-paper report treatment. It creates a meaningful contrast with the dark workspace and is the strongest cross-page design decision. [Desktop report](../.playwright-cli/design-desktop-report-studio.png).

| Priority | Control / state | Observed visual issue | Design fix |
|---|---|---|---|
| **P0** | Mobile edit controls | The entire long paper preview comes before **Structure**, **Include**, **Cite**, confidence language, and Export PDF. The first structure button sits around **y=2,700 px**; export is near **y=3,850 px**. [Mobile report](../.playwright-cli/design-mobile-report-studio.png). | Use **Edit / Preview** modes on phone. Open on an edit summary with section navigation and key controls; put paper behind Preview. Keep an accessible action bar near the top. |
| **P1** | Desktop/768 page actions | Save draft, Print preview, and Request approval float at the far right; at 768–1024 px they wrap into an uneven stack. [768 px](../.playwright-cli/design-768-report-studio.png). | Establish a persistent action hierarchy: Save, Preview, then a separated approval action. Use a compact action menu at tablet widths. |
| **P1** | Structure list | Clicking a section changes only the highlighted row; the paper remains visually in the same place. [Clicked state](../.playwright-cli/state-report-section.png). | Make selection visibly correspond to the section in the preview: scroll to it, outline it briefly, and show its editing controls. |
| **P2** | Include/Cite lists | The control column becomes long, with many similar checkboxes and no category summary. | Group by evidence and finding type; show “6 findings included / 3 sources cited” and reveal detailed choices on demand. |
| **P2** | Paper typography | The serif paper is appropriate, but 13 px finding rows and small metadata make the draft dense at normal desktop scale. | Use a slightly more generous report reading size and line spacing; keep compact IDs in the margin. Preserve printable proportions. |
| **P2** | Export PDF placement | Export sits at the bottom of the right editor column, disconnected from Save and Preview. | Put export beside Preview or in the top action group, with the final-export action visually distinct from draft operations. |

### 6. Governance

**Keep:** the timeline-like ledger and semantic colors for verified/revoked states. The desktop view is orderly. [Desktop governance](../.playwright-cli/design-desktop-governance.png).

| Priority | Control / state | Observed visual issue | Design fix |
|---|---|---|---|
| **P1** | Mobile event rows | Each event stacks title, timestamp/type, actor, and verification with large vertical gaps; eight events create a very long page. [Mobile governance](../.playwright-cli/design-mobile-governance.png). | Use one-line title, a compact metadata line, and an aligned status; expand a row for actor and technical detail. |
| **P1** | Mobile filter order | Six event-type toggles occupy the first screen before the ledger begins. | Replace with a horizontal filter trigger and selected-filter summary. The ledger should be visible within the first phone viewport. |
| **P2** | Desktop three-column split | Event filters, ledger, and model/retention panels all read as equally enclosed blocks. | Give the ledger the strongest width and contrast. Move model and retention information into a quieter secondary summary. |
| **P2** | Export log | The text-only action sits in the far-right heading area and becomes a lonely line under the mobile introduction. | Align export with the ledger title and filters; keep it secondary to reading the record. |
| **P2** | Filtered state | Unchecking Export reduces the ledger from eight to seven events, but the active filter set is not summarized above results. [Clicked state](../.playwright-cli/state-governance-filtered.png). | Show the filter count and a “Clear filters” affordance next to “7 events.” |

## Proposed visual system

This is a refinement of the existing identity, not a new theme.

- **Color:** retain `#0B0A09` base, `#F3EEE6` main text, and `#E9A23B` primary action. Use `#F0604D` only for suspicious findings, `#7FA6BF` for review, and `#8FBF7A` for verified states. Keep `#5F5A52` away from operational labels and small metadata.
- **Type:** use the current sans for interface hierarchy and the serif only for document content. Target 16 px reading text, 14 px control labels, and 13 px technical metadata. Monospace is for identifiers and measured values, not general navigation.
- **Spacing:** keep a consistent 8 px unit, with 16–24 px within active panels and 24–32 px between task groups. On desktop, allow more open space *between* tasks rather than adding borders around each subpart.
- **Buttons:** one amber primary action per local context. Secondary actions should remain discoverable with a stable outline or text treatment. Pressed, selected, disabled, hover, focus, loading, and menu-open states need clearly different appearances.
- **Canvas:** evidence imagery and the graph can use full-bleed space. Timeline and metadata should size to their content and use spare room for selected evidence, explanations, or comparison rather than empty black.
- **Motion:** use 150–220 ms for controls, 220–300 ms for panels, and stop movement once a state is settled. Motion should explain a change in evidence or focus, never make work feel busy. Respect reduced motion.
- **Mobile:** treat phone layouts as a separate investigation mode: one primary task, one stable context line, one place to reveal tools. Do not rely on hidden horizontal strips for core actions.

### Signature design opportunity

Make a **selected finding** the connective visual unit across Command centre → Investigation → Graph → Report. A consistent finding marker, excerpt, time range, and status should travel between views. The user should feel they are tracing one piece of evidence through the system, not opening unrelated dashboards. This would give NEXTRON a distinctive interaction language without gratuitous animation.

## URL and navigation design

The live site does **not** expose a literal `/page` URL. Its current views use URLs such as `/workspace?view=report&case=NX-10487`; `page.tsx` is a source filename, not a public address. The current URL already records more state than before. For a polished product, move primary destinations and entities into **semantic paths** and use query parameters only for temporary view settings.

| Current | Recommended public path | Why |
|---|---|---|
| `/workspace?view=command` | `/workspace` | A short, stable entry point. |
| `/workspace?view=intake` | `/workspace/intake` | Clear destination for scanning evidence. |
| `/workspace?view=investigate&case=NX-10487&evidence=EV-0194` | `/workspace/cases/NX-10487/evidence/EV-0194` | The case and evidence are real navigable objects. |
| `/workspace?view=graph&case=NX-10487` | `/workspace/cases/NX-10487/graph` | The graph belongs to a case. |
| `/workspace?view=report&case=NX-10487` | `/workspace/cases/NX-10487/report` | Shareable report location. |
| `/workspace?view=audit` | `/workspace/governance` | Clear and durable destination. |

Example of the punctuation the user mentioned, **used where it has a purpose**:

`/workspace/cases/NX-10487/evidence/EV-0194?tool=timeline&finding=F-021#frame-712`

Here `?` begins view/filter parameters, `&` separates them, and `#` links to a meaningful in-page point. `%` appears only when URL encoding requires it; it is not a design feature. Avoid `?view=` for primary navigation and avoid meaningless `?#%` strings. A custom production domain is a separate deployment decision; `localhost:3000` is only a local development address.

**Route acceptance criteria:** refresh and copied links reopen the same case/evidence; Back and Forward move between meaningful destinations; unknown IDs show a designed recovery state; canonical paths are consistent in navigation and breadcrumbs. Route implementation should be planned after the design hierarchy is agreed, since paths are part of the user journey.

## Delivery order

| Stage | Work | Size | Visual acceptance |
|---|---|---|---|
| 1 | Repair 768 px header/breadcrumb and mobile graph control collision/legend | S–M | No overlap; every visible control can reveal its state. |
| 2 | Recompose phone investigation controls, timeline, and finding sheet | M–L | Current case/tool/selected clue stay visible; key actions do not hide offscreen. |
| 3 | Separate phone report Edit and Preview; bring decisions up on phone Command centre | M | Editing begins in the first screen; urgent work is apparent immediately. |
| 4 | Apply unified type, spacing, target sizes, and selected states across all six views | M | Controls feel related without flattening the distinct viewer/report compositions. |
| 5 | Connect the selected finding visually across views; refine graph labels and inspector | L | The same clue is recognizable from queue to final report. |
| 6 | Implement semantic URL paths and test responsive navigation states | M | Shareable paths, accurate breadcrumbs, safe Back/Forward behavior. |

## Final quality gate

- Test **360, 390, 768, 900, 1024, 1280, 1440, and 1920 px** with actual click states, not only initial screens.
- Capture every major view with its **menu, selection, inspector, filtered, empty, loading, and error** states as applicable.
- Verify no header text wraps into fixed-height controls and no canvas action is covered by another element.
- Verify that the primary action, current case/evidence, and selected finding are visually clear on a phone.
- Check touch targets, 200% zoom, keyboard focus, reduced motion, and light report/print contrast.
- Confirm route names and breadcrumbs read like a professional investigation product.
- Judge the final experience as **one evidence-led system**, not six individually attractive screens. Award recognition cannot be guaranteed; these are the changes most likely to make the experience distinctive and complete.
