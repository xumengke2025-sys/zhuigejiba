# Medieval Map Design Specification

## 1. Visual Style Overview
- **Theme**: Antique Parchment / Medieval Cartography
- **Texture**: Aged paper background with burnt/vignetted edges.
- **Line Work**: Hand-drawn ink style, variable line width, hatching for shadows.
- **Atmosphere**: Historical, mysterious, exploration-focused.

## 2. Color Palette
| Usage | Color | Hex | Description |
|-------|-------|-----|-------------|
| **Background** | Antique Parchment | `#e8dcb5` | Base paper color |
| **Water (Deep)** | Dark Slate Gray | `#2f4f4f` | Deep ocean areas |
| **Water (Shallow)** | Faded Blue-Green | `#6b8e8e` | Coastal waters |
| **Ink / Text** | Very Dark Brown | `#2c1b18` | Main text and outlines |
| **Border** | Dark Brown | `#3d2b1f` | Map frame and heavy lines |
| **Accent (Gold)** | Dull Gold | `#c5a059` | Highlights, capitals, special markers |
| **Accent (Red)** | Dark Red | `#8b0000` | Seals, routes, important events |
| **Forest** | Dark Olive Green | `#2f3d26` | Vegetation areas |
| **Mountain** | Bronze/Brown | `#5a4632` | Elevation features |

## 3. Icon System
All icons should simulate hand-drawn ink illustrations.

- **Mountain**: Jagged peaks with hatching on the shadow side.
- **Water**: Stylized wave lines and swirls. No solid blue fills (use texture).
- **Forest**: Clusters of individual tree icons (deciduous/pine mix) rather than solid blobs.
- **City**:
  - **Capital**: Castle/Keep with towers and flags.
  - **Town**: Walled enclosure with small house clusters.
  - **Village**: Simple house shapes.
- **Roads**: Dashed lines or "footprint" paths.
- **Special**: Towers for temples, ruins for abandoned sites.

## 4. Typography
- **Headlines / Titles**: `IM Fell English SC` (Google Fonts). Gothic/blackletter feel but readable.
- **Labels**: `IM Fell English` or similar serif with rough edges.
- **Decorations**: Large drop caps, swashes on first/last letters.

## 5. Interactions & Animations
- **Hover**:
  - Cursor changes to a quill or hand.
  - Tooltips appear as small parchment scraps with ragged edges.
  - Elements subtly scale or glow (gold outline).
- **Click**:
  - "Wax Seal" effect: A red seal appears briefly on click target.
  - Sound effect (optional): Paper rustle or quill scratch.
- **Transitions**:
  - Map load: Ink diffusion effect (mask revealing map from center).
  - Zoom: Smooth scaling with detail fading in/out (LOD).

## 6. Technical Implementation
- **Rendering**: HTML5 Canvas (2D Context) for main map.
- **Effects**:
  - CSS3 Filters (`sepia`, `contrast`) for overall tone.
  - SVG filters for paper texture (turbulence/displacement).
  - `globalCompositeOperation` for masking borders and textures.
- **Performance**:
  - Use offscreen canvas for static background layers.
  - Batch render icons.
  - Spatial indexing (Quadtree/Grid) for interaction hit-testing.
