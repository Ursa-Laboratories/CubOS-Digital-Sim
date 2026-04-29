# Digital Twin Rebuild Summary

Rebuilt the CubOS digital twin from scratch on `ben/rebuild-digital-twin`.

## What changed

- Replaced the old Python exporter with a clean CubOS-backed export pipeline:
  - `src/digital_twin/exporter.py`
  - `src/digital_twin/motion.py`
  - `src/digital_twin/geometry.py`
  - `src/digital_twin/cli.py`
- Replaced the old viewer with a new React + Three.js first-pass simulator:
  - CubOS deck coordinate frame: `+X` right, `+Y` back/away, `+Z` up
  - deck working volume and axes
  - labware/vial AABB geometry
  - gantry bridge/carriage
  - attached instrument envelope
  - protocol timeline
  - granular interpolated motion path
  - first-pass AABB collision/proximity warnings
- Generated a real example bundle from CubOS Sterling configs:
  - `viewer/public/examples/sterling-vial-scan.json`
  - `viewer/dist/examples/sterling-vial-scan.json`
- Added a static fallback render for this environment:
  - `progress/static-render.svg`
- Updated docs:
  - `README.md`
  - `viewer/README.md`
- Cleaned tracked Python cache artifacts from the old implementation.

## Verification results

Python tests:

```bash
PYTHONPATH=/home/achan/.openclaw/workspace/CubOS-Digital-Sim/src:/home/achan/.openclaw/workspace/Ursa-CubOS/src /home/achan/.openclaw/workspace/.worktrees/cubos-issue-61-safe-gantry-move/.venv/bin/python -m pytest -q
```

Result:

```text
6 passed in 0.50s
```

Sample export:

```bash
PYTHONPATH=/home/achan/.openclaw/workspace/CubOS-Digital-Sim/src:/home/achan/.openclaw/workspace/Ursa-CubOS/src /home/achan/.openclaw/workspace/.worktrees/cubos-issue-61-safe-gantry-move/.venv/bin/python -m digital_twin --cubos-root /home/achan/.openclaw/workspace/Ursa-CubOS --gantry /home/achan/.openclaw/workspace/Ursa-CubOS/configs/gantry/cub_xl_sterling.yaml --deck /home/achan/.openclaw/workspace/Ursa-CubOS/configs/deck/sterling_deck.yaml --protocol /home/achan/.openclaw/workspace/Ursa-CubOS/configs/protocol/sterling_vial_scan.yaml --out /tmp/sterling-check.json --sample-step-mm 5
```

Result:

```json
{
  "out": "/tmp/sterling-check.json",
  "labware": 1,
  "timelineSteps": 12,
  "pathSamples": 451,
  "warnings": 94
}
```

Frontend tests:

```bash
cd viewer && npm test
```

Result:

```text
Test Files  1 passed (1)
Tests  2 passed (2)
```

Note: stderr included `WARNING: Multiple instances of Three.js being imported.`

Frontend build:

```bash
cd viewer && npm run build
```

Result:

```text
✓ 613 modules transformed.
dist/index.html                     0.40 kB │ gzip:   0.27 kB
dist/assets/index-BGxEeA_F.css      1.69 kB │ gzip:   0.75 kB
dist/assets/index-Dq2WJDxa.js   1,109.70 kB │ gzip: 317.69 kB
✓ built in 7.43s
```

Note: Vite warned the main JS chunk is larger than 500 kB.

Local static serving check:

```bash
cd viewer/dist && python3 -m http.server 4173 --bind 127.0.0.1
curl -I --max-time 5 http://127.0.0.1:4173/
curl -s --max-time 5 http://127.0.0.1:4173/examples/sterling-vial-scan.json | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["schemaVersion"], len(d["motion"]["path"]), len(d["warnings"]))'
```

Result:

```text
HTTP/1.0 200 OK
digital-twin.v1 451 94
```

Browser availability:

```bash
command -v chromium || command -v chromium-browser || command -v google-chrome || command -v firefox || command -v playwright || true
```

Result: no browser executable or Playwright install was available in this environment. The static server and generated SVG fallback were used for local render sanity checks.

## Remaining risks

- Collision warnings are intentionally first-pass AABB/proximity checks, not exact swept-volume geometry.
- Motion interpolation is protocol/geometric linear interpolation. It does not model GRBL acceleration or controller timing.
- The viewer JS bundle is large because Three.js and drei are bundled together; code splitting can be a follow-up.
