# TODO: Pixel Art Assets

These asset packs should be downloaded and extracted into `frontend/src/assets/pixel/` to replace generated placeholders.

## Required Packs

### 1. Ansimuz Sunny Land
- **URL**: https://ansimuz.itch.io/sunny-land-pixel-game-art
- **License**: CC0 / Free
- **Extract to**: `backgrounds/` (sky layers, clouds, hills, ground), `characters/` (player sprites)
- **Replaces**: `backgrounds/hero-scene.png` (currently a PIL-generated placeholder)

### 2. Kenney Pixel Platformer ✅ Downloaded
- **URL**: https://kenney.nl/assets/pixel-platformer
- **License**: CC0
- **Status**: Extracted to `kenney_pixel_platformer/`
- **Used**: `characters/kenney-characters.png`, `backgrounds/kenney-backgrounds.png`

### 3. Quintino Pixel UI
- **URL**: https://quintino-pixels.itch.io/pixel-ui
- **License**: Free for commercial use
- **Extract to**: `ui/` (wood panel frames, buttons, pixel borders)
- **Replaces**: CSS-only `.wood-panel` styling

## Current Placeholders

| Asset | Current State | Target |
|-------|--------------|--------|
| Hero background | PIL-generated `hero-scene.png` | Ansimuz Sunny Land layered parallax |
| Mentor character | Kenney sprite sheet crop | Full sprite sheet with idle animation frames |
| Wood panel frame | CSS border + shadow | Quintino 9-slice pixel frame |
| Journey map bg | PIL-generated `journey-map-bg.png` | Proper pixel tilemap ground |

## Asset Integration Rules (from PRD §13)

- Keep assets in `frontend/src/assets/pixel/`
- Use `image-rendering: pixelated` when scaling
- Use `object-fit` / `object-position` for responsive sizing
- Do not stretch non-proportionally
- Document license near each asset
