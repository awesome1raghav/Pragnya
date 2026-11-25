# VANAVAASAM landing

The user-supplied landing image controls the public design. The existing NEXTRON investigator interface remains at `/workspace`; `/` now presents Team VANAVAASAM.

## Source interpretation

Team VANAVAASAM.pdf, pages 3–4: video input (MP4, MOV, WebM), preprocessing, spatial/temporal/audio-visual branches, evidence fusion, localization, uncertainty, reporting. Pages 1 and 8 provide team and institute attribution. Research material is described as project direction, not measured product accuracy. The slide's market forecasts and numerical performance claims are not used as product claims.

## Visual extraction

Desktop: black background, warm amber accents, left headline around 80px at 1600px, a larger right product preview, a thin ruled capability strip. Off-white CTA, restrained 6–15px radii, hairline borders. Sans-serif public typography is separate from the archival workspace typography. The portrait is a generated fictional demonstration asset; all text, controls, dividers, signal overlays and layout are real UI.

## Motion

GSAP entrance: 850ms staggered copy reveal, 1100ms console reveal. Ambient scan: 4500ms sweep plus 1500ms rest. Signal field: slow sine movement. Framer Motion: 180ms mode transitions and 200ms workflow transitions. Motion pause control reverts ambient timelines; reduced-motion preference disables ambient motion and entrance displacement. No automatic mode switching or scroll interception.

## Image generation

Built-in image generation was used. `landing-reference.png` is a new design reference derived from the user's supplied image. Prompt: preserve the composition, near-black background, amber accent, off-white grotesk typography, VANAVAASAM navigation, two-line headline, analysis demonstration, spatial/temporal/audio-visual controls, and bottom evidence capability row.

`../public/images/forensic-portrait.png` is the production asset. Prompt: a single 4:5 close frontal photographic portrait of a fictional young adult man with wavy dark hair, dark shirt, neutral expression, crisp grayscale photography and deep black background; no UI, text, overlays or logos. The coded comparison applies colored presentation overlays only; they are not model-produced evidence.

## Checks and limits

Production Next.js build, browser screenshots, mobile overflow, mode selection and motion pause/reduced-motion checks. The analyzer is the previously built frontend prototype. No inference backend or authentication was added as part of this landing implementation.
