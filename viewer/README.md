# Digital Twin Viewer

React + Three.js viewer for JSON bundles exported by `python -m digital_twin`.
The first screen is the usable simulation: deck volume, axes, labware/wells,
gantry bridge/carriage, active instrument envelope, protocol timeline, motion
path, and first-pass AABB warnings.

## Default Example

The checked-in example bundle is generated from real CubOS Sterling configs:

- `configs/gantry/cub_xl_sterling.yaml`
- `configs/deck/sterling_deck.yaml`
- `configs/protocol/sterling_vial_scan.yaml`

The bundle lives at `public/examples/sterling-vial-scan.json`.

## Development

```bash
npm install
npm test
npm run build
npm run dev
```

The viewer maps CubOS `(x, y, z)` to Three.js `(x, z, -y)`, preserving CubOS
deck semantics while using Three.js's Y-up world.
