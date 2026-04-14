import json
from pathlib import Path

from digital_twin.exporter import export_bundle, export_bundle_to_path


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "examples" / "configs"


def test_export_bundle_builds_expected_move_trace():
    bundle = export_bundle(
        gantry_path=CONFIGS / "gantry/cubos.yaml",
        deck_path=CONFIGS / "deck/mofcat_deck.yaml",
        board_path=CONFIGS / "board/mock_mofcat_board.yaml",
        protocol_path=CONFIGS / "protocol/move.yaml",
    )

    assert bundle["summary"]["step_count"] == 1
    assert bundle["summary"]["timeline_event_count"] == 1
    assert [event["phase"] for event in bundle["timeline"]] == ["move_xyz"]
    assert bundle["timeline"][0]["instrument_id"] == "uvvis"
    assert bundle["timeline"][0]["target_label"] == "plate_1.A1"
    assert bundle["scene"]["contract_version"] == "cubos-deck-base-z0-v2"
    first_item = bundle["scene"]["deck"][0]
    assert first_item["placement_anchor"] is None
    assert first_item["default_target"] == {"x": 17.88, "y": 42.23, "z": 20.0}
    assert first_item["named_targets"][0] == {
        "id": "A1",
        "position": {"x": 17.88, "y": 42.23, "z": 20.0},
    }
    assert bundle["timeline"][-1]["end_tip_pose"] == {
        "x": 17.88,
        "y": 42.23,
        "z": 23.0,
    }


def test_export_bundle_reflects_offset_tip_pose(tmp_path):
    board_path = tmp_path / "board.yaml"
    board_path.write_text(
        """
instruments:
  uvvis:
    type: uvvis_ccs
    vendor: thorlabs
    offset_x: 10.0
    offset_y: -5.0
    depth: 7.0
    measurement_height: 3.0
""".strip()
        + "\n"
    )

    bundle = export_bundle(
        gantry_path=CONFIGS / "gantry/cubos.yaml",
        deck_path=CONFIGS / "deck/mofcat_deck.yaml",
        board_path=board_path,
        protocol_path=CONFIGS / "protocol/move.yaml",
    )

    final_event = bundle["timeline"][-1]
    assert final_event["end_gantry_pose"] != final_event["end_tip_pose"]
    assert final_event["end_gantry_pose"] == {
        "x": 7.879999999999999,
        "y": 47.23,
        "z": 16.0,
    }
    assert final_event["end_tip_pose"] == {
        "x": 17.88,
        "y": 42.23,
        "z": 23.0,
    }


def test_export_bundle_to_path_writes_json(tmp_path):
    output_path = tmp_path / "bundle.json"
    export_bundle_to_path(
        gantry_path=CONFIGS / "gantry/cubos.yaml",
        deck_path=CONFIGS / "deck/mofcat_deck.yaml",
        board_path=CONFIGS / "board/mock_mofcat_board.yaml",
        protocol_path=CONFIGS / "protocol/move.yaml",
        output_path=output_path,
    )

    saved = json.loads(output_path.read_text())
    assert saved["summary"]["timeline_event_count"] == 1


def test_export_bundle_supports_scan_protocol():
    bundle = export_bundle(
        gantry_path=CONFIGS / "gantry/cubos.yaml",
        deck_path=CONFIGS / "deck/mofcat_deck.yaml",
        board_path=CONFIGS / "board/mock_mofcat_board.yaml",
        protocol_path=CONFIGS / "protocol/cubos_scan_test.yaml",
    )

    motion_events = [event for event in bundle["timeline"] if event["type"] == "motion"]
    action_events = [event for event in bundle["timeline"] if event["type"] == "action"]

    assert bundle["summary"]["step_count"] == 2
    assert len(motion_events) == 96
    assert len(action_events) == 96
    assert motion_events[0]["target_label"] == "plate_1.A1"
    assert action_events[0]["target_label"] == "plate_1.A1"
    assert action_events[1]["target_label"] == "plate_1.A2"
    assert action_events[-1]["target_label"] == "plate_1.H12"
    assert all(event["kind"] == "measure" for event in action_events)


def test_export_bundle_can_skip_validation_for_visualization_combo():
    bundle = export_bundle(
        gantry_path=CONFIGS / "gantry/cubos_xl.yaml",
        deck_path=CONFIGS / "deck/panda_deck.yaml",
        board_path=CONFIGS / "board/asmi_board.yaml",
        protocol_path=CONFIGS / "protocol/asmi_panda_deck_test.yaml",
        skip_validation=True,
    )

    assert bundle["summary"]["validation_skipped"] is True
    assert bundle["summary"]["validation_violation_count"] == 0
    assert bundle["timeline"][0]["target_label"] == "well_plate_holder.plate.A1"


def test_export_bundle_supports_two_instrument_visualization_protocol():
    bundle = export_bundle(
        gantry_path=CONFIGS / "gantry/cubos_xl.yaml",
        deck_path=CONFIGS / "deck/two_instrument_deck.yaml",
        board_path=CONFIGS / "board/two_instrument_board.yaml",
        protocol_path=CONFIGS / "protocol/two_instrument_visualization_test.yaml",
    )

    motion_events = [event for event in bundle["timeline"] if event["type"] == "motion"]
    assert bundle["summary"]["step_count"] == 9
    assert bundle["summary"]["timeline_event_count"] == 10
    assert motion_events[0]["instrument_id"] == "liquid_handler"
    assert motion_events[0]["target_label"] == "tip_rack.A1"
    assert any(event["instrument_id"] == "potentiostat" for event in motion_events)
    assert motion_events[-1]["target_label"] == "tip_disposal"
