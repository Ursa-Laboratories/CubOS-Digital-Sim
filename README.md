# CubOS Digital Twin

Standalone digital twin package for CubOS. This package depends on CubOS as a
Python dependency and provides:

- `python -m digital_twin` bundle export
- a browser viewer under `viewer/`

## Install

For a normal install, the package depends on CubOS from the
`refactor-z-coordinates` branch on GitHub:

```bash
pip install .
```

For local development against this workspace's CubOS checkout on
`refactor-z-coordinates`:

```bash
pip install -e /path/to/CubOS
pip install --no-deps -e /path/to/CubOS/digital-twin
```

## Export

From inside this package:

```bash
python -m digital_twin \
  --gantry ../configs/gantry/cubos_xl.yaml \
  --deck ../configs/deck/two_instrument_deck.yaml \
  --board ../configs/board/two_instrument_board.yaml \
  --protocol ../configs/protocol/two_instrument_visualization_test.yaml \
  --out viewer/public/examples/two-instrument-cubos-xl.json
```

## Viewer

The browser viewer lives in `viewer/`.

## Contributor Workflow

Repository-specific working guidance for Codex and other agents lives in
`AGENTS.md`. Progress for each chat is recorded in dated files under
`progress/`.
