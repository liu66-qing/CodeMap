# Stage Pixel Component Library

This folder stores transparent PNG components generated with the same pet-style sprite workflow, so Stage pages can reuse one visual language without touching the homepage.

## Character Sprites

- `mentor-runner.png`: Stage 2 route-running mentor.
- `mentor-miner.png`: Stage 3 mining / deep-dive mentor.
- `mentor-trophy.png`: Stage 4 completion mentor.

## Stage Props

- `wood-arrow-sign.png`: blank wooden route sign.
- `route-arrow-blue.png`: glowing route guide arrow.
- `crystal-memory-purple.png`: memory / system-core crystal.
- `crystal-agent-blue.png`: agent entity crystal.
- `crystal-loop-green.png`: loop / feedback crystal.
- `campfire-crates.png`: takeaway campfire and crates.
- `mine-entrance.png`: blank mine entrance prop.
- `badge-clipboard.png`: task / checklist badge.
- `badge-map.png`: map / global-view badge.

## Overview Props

Overview-specific first-pass crops live in `../overview` and are exported through `index.ts` as `overviewAssets`:

- `farm-mentor.png`: Stage 1 pastoral guide.
- `wood-board.png`: Stage 1 one-sentence positioning board.
- `decor-bridge.png`, `decor-chest.png`, `decor-flag.png`, `decor-flowers.png`, `decor-grass.png`, `decor-sign.png`, `decor-stones.png`, `decor-stump.png`: card decorations.

## Typography Direction

No local font file is committed yet. The current page uses CSS pixel outlining for the Chinese title and keeps the implementation local. Recommended future font candidates:

- English stage text: Press Start 2P style pixel font.
- Chinese title text: a Chinese bitmap/pixel font with full CJK coverage, such as a Zpix/Fusion Pixel style family, added locally as `.woff2`.
