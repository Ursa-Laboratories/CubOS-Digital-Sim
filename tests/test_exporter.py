from pathlib import Path

from digital_twin.exporter import SCHEMA_VERSION, export_digital_twin, write_digital_twin


CUBOS_ROOT = Path("/home/achan/.openclaw/workspace/Ursa-CubOS")


def test_exporter_loads_real_cubos_configs():
    data = export_digital_twin(
        cubos_root=CUBOS_ROOT,
        gantry_path=CUBOS_ROOT / "configs/gantry/cub_xl_sterling.yaml",
        deck_path=CUBOS_ROOT / "configs/deck/sterling_deck.yaml",
        protocol_path=CUBOS_ROOT / "configs/protocol/sterling_vial_scan.yaml",
        sample_step_mm=25,
    )

    assert data["schemaVersion"] == SCHEMA_VERSION
    assert data["coordinateSystem"]["axes"]["+z"] == "up"
    assert data["gantry"]["workingVolume"]["x_max"] == 306.0
    assert data["deck"]["labware"][0]["key"] == "vial_holder"
    assert len(data["deck"]["labware"][0]["children"]) == 8
    assert len(data["protocol"]["timeline"]) == 12
    assert data["motion"]["path"]


def test_write_digital_twin_creates_parent_dirs(tmp_path):
    out = tmp_path / "nested" / "sample.json"

    data = write_digital_twin(
        cubos_root=CUBOS_ROOT,
        gantry_path=CUBOS_ROOT / "configs/gantry/cub_xl_sterling.yaml",
        deck_path=CUBOS_ROOT / "configs/deck/sterling_deck.yaml",
        protocol_path=CUBOS_ROOT / "configs/protocol/sterling_vial_scan.yaml",
        out_path=out,
        sample_step_mm=50,
    )

    assert out.exists()
    assert "sterling_vial_scan.yaml" in data["source"]["protocol"]
