# CubOS Digital Twin

Clean first-pass digital twin for CubOS. The Python exporter loads CubOS
gantry, deck, and protocol YAML through CubOS loader APIs, then emits a
frontend-friendly JSON bundle for a React + Three.js viewer.

Coordinate convention follows CubOS deck space: front-left-bottom origin,
`+X` right, `+Y` away/back, and `+Z` up.

## Export

Use a local CubOS checkout as the source of truth:

```bash
python -m digital_twin \
  --cubos-root /home/achan/.openclaw/workspace/Ursa-CubOS \
  --gantry /home/achan/.openclaw/workspace/Ursa-CubOS/configs/gantry/cub_xl_sterling.yaml \
  --deck /home/achan/.openclaw/workspace/Ursa-CubOS/configs/deck/sterling_deck.yaml \
  --protocol /home/achan/.openclaw/workspace/Ursa-CubOS/configs/protocol/sterling_vial_scan.yaml \
  --out viewer/public/examples/sterling-vial-scan.json
```

The exported schema includes:

- CubOS working volume, home pose, instruments, offsets, and approach heights.
- Deck labware, contained labware, wells/tips/slots, and first-pass AABB geometry.
- Protocol timeline with named positions.
- Interpolated step-by-step TCP and gantry motion path.
- AABB collision/proximity warnings against non-target labware.

## Viewer

The browser viewer lives in `viewer/` and loads
`public/examples/sterling-vial-scan.json` by default.

```bash
cd viewer
npm install
npm test
npm run build
```

In this container, local server/browser verification may be blocked by missing
browser binaries or port-listen restrictions. `progress/static-render.svg` is
the generated static render fallback from the same JSON bundle.
