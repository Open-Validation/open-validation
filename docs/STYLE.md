# Explorer visual style

**A dark blueprint.** Deep blueprint-navy background with a faint white squared-paper grid, white
linework, flat shapes, no gradients or shadows. Think "architect's drawing on blueprint paper".
Dark is the only theme. It must look independent: no GOV.UK crown, typeface, black header or
anything that could be mistaken for a council or government service.

## Colour (CSS variables on `:root`)

| Variable | Value | Use |
|---|---|---|
| `--bg` | `#0B1F3A` | page |
| `--surface` | `#112B4E` | cards, panels, table cells |
| `--grid` | `rgba(255,255,255,0.06)` | faint 24px page grid |
| `--line` | `rgba(255,255,255,0.6)` | table grid lines, card borders |
| `--text` | `#F2F6FB` | text |
| `--text-muted` | `#A8BEDB` | secondary text, "Not required" |
| `--accent` | `#7FB2F0` | links, buttons, "Required" |
| `--check` | `#F2B705` | "Check" (always a dashed edge and a "?") |

### Review-status colours

| Status | Variable | Colour | Contrast vs `--bg` | Cell tint (20% over `--surface`) | `--text` on tint |
|---|---|---|---|---|---|
| incorrect | `--status-incorrect` | `#B388FF` purple | 6.2 | `#313E71` | 9.4 |
| unverified | `--status-unverified` | `#EF5350` red | 4.7 | `#3D334E` | 10.9 |
| human-verified | `--status-human` | `#FB8C00` orange | 7.0 | `#403E3E` | 9.8 |
| council-verified | `--status-council` | `#43A047` dark green | 5.0 | `#1B424D` | 10.0 |
| council-updated | `--status-updated` | `#AED581` light green | 9.9 | `#304D58` | 8.3 |
| not covered yet | `--status-out` | `#3A4A60` grey | 1.8 (so it has a 1px `--line` border) | n/a | n/a |

All pass WCAG AA: status colours are at least 3:1 against the background, and text on every tint
is at least 4.5:1. Dark and light green differ by about 2:1 in luminance, and the Patterns
toggle gives each status its own texture as well.

- **Map fills and status badges** use the full colours. Badge text is `--bg` (dark), which reads
  at 4.7:1 or better on every status colour.
- **Table cells** use the washed-out tint (the status colour at 20% opacity over `--surface`)
  plus a 3px solid stripe of the full colour down the cell's left edge, so dark green still shows
  against navy. Text stays `--text`. `incorrect` cells also show a ✕.
- **Keep orange away from amber:** status colours appear only as map fills, cell tints and
  small solid badges with the status written in them. "Check" is always a dashed amber card
  edge with a "?" icon.
- **Patterns** (legend toggle, for colour-blind users): unverified none, human-verified dots,
  council-verified diagonal lines, council-updated cross-hatch, incorrect horizontal lines; the
  grey stays plain.

### Result cards

- **Required:** solid `--accent` left edge and a filled tick icon.
- **Check:** dashed `--check` edge and a "?" icon.
- **Not required:** muted outline and `--text-muted` text; collapsed by default.

## Type

IBM Plex Sans (400, 600) from Google Fonts for text; IBM Plex Mono for file names, YAML and table
cells that hold codes. Large, plain headings.

## Shapes

- Site pills: 999px radius. Unknown = white 1px outline; yes = filled `--accent` with `--bg`
  text; no = struck through, `--text-muted`.
- Cards: 12px radius, 1px `--line` border. Tables: 1px `--line` border on every cell, no zebra
  stripes (the status tints do that job). Header row semi-bold `--text` on `--bg`.
- Generous spacing. Visible focus outline (2px `--accent`) on everything focusable.

## Illustrations

A few small inline SVGs drawn as thin white line drawings, like linework on a blueprint: a pin-up
board with a site plan (empty state), a document stack (loading), a phone (the submission pack's
"pay the council" screen). Only for empty, loading and final screens. Simple shapes, no stock images.

## Security

js-yaml and d3 load from pinned jsDelivr URLs with Subresource Integrity hashes. A
Content-Security-Policy meta tag allows scripts only from the page itself and cdn.jsdelivr.net,
and network requests only to the page's own site and api.github.com. The review-mode token is
kept in `sessionStorage`, sent only to api.github.com, and never logged or put in a URL.
