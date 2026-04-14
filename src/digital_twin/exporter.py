"""Export CubOS protocol traces into a browser-friendly digital twin bundle."""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from board import Board, BoardYamlSchema, load_board_from_yaml_safe
from deck import (
    Deck,
    DeckYamlSchema,
    HolderLabware,
    TipDisposal,
    TipRack,
    TipRackYamlEntry,
    Vial,
    VialHolder,
    VialHolderYamlEntry,
    VialYamlEntry,
    Wall,
    WellPlate,
    WellPlateHolder,
    WellPlateHolderYamlEntry,
    WellPlateYamlEntry,
    load_deck_from_yaml_safe,
)
import deck.labware.definitions.registry as definition_registry
from deck.labware.definitions.registry import load_definition_config, load_registry
from deck.yaml_schema import NestedVialYamlEntry, NestedWellPlateYamlEntry
from gantry import GantryConfig, load_gantry_from_yaml_safe
from protocol_engine import Protocol, ProtocolContext, ProtocolStep, load_protocol_from_yaml_safe
from validation import SetupValidationError, validate_deck_positions, validate_gantry_positions


_SUPPORTED_PHASE_ONE_COMMANDS = {"move", "scan"}
_DEFAULT_FEED_RATE = 2000.0
_Z_TOLERANCE_MM = 1e-4


@dataclass(frozen=True)
class MotionPose:
    x: float
    y: float
    z: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True)
class MotionSegmentPlan:
    phase: str
    start_pose: MotionPose
    end_pose: MotionPose
    feed_rate: float
    distance_mm: float
    real_duration_s: float


def _load_yaml(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Expected YAML mapping at {path}, got {type(raw).__name__}.")
    return raw


def _coerce_motion_pose(coord: Any) -> MotionPose:
    if isinstance(coord, MotionPose):
        return coord
    if isinstance(coord, dict):
        return MotionPose(x=float(coord["x"]), y=float(coord["y"]), z=float(coord["z"]))
    if isinstance(coord, (tuple, list)) and len(coord) == 3:
        return MotionPose(x=float(coord[0]), y=float(coord[1]), z=float(coord[2]))
    return MotionPose(x=float(coord.x), y=float(coord.y), z=float(coord.z))


def _coord_dict(coord: Any) -> dict[str, float]:
    return _coerce_motion_pose(coord).to_dict()


def _coord_key(coord: Any) -> tuple[float, float, float]:
    pose = _coerce_motion_pose(coord)
    return (round(pose.x, 6), round(pose.y, 6), round(pose.z, 6))


def _format_target_label(target: Any) -> str:
    if isinstance(target, str):
        return target
    if isinstance(target, (list, tuple)):
        return "[" + ", ".join(f"{float(value):.3f}" for value in target) + "]"
    return str(target)


def _event_base_duration(event: dict[str, Any]) -> float:
    if event["type"] == "motion":
        return max(float(event["real_duration_s"]), 0.05)
    return max(float(event.get("duration_s", 0.0)), 0.0)


def _distance_mm(start_pose: MotionPose, end_pose: MotionPose) -> float:
    return math.dist(
        (start_pose.x, start_pose.y, start_pose.z),
        (end_pose.x, end_pose.y, end_pose.z),
    )


def _duration_s(distance_mm: float, feed_rate: float) -> float:
    if distance_mm <= 0:
        return 0.0
    if feed_rate <= 0:
        return 0.0
    return distance_mm / feed_rate * 60.0


def _segment_phase(start_pose: MotionPose, end_pose: MotionPose) -> str:
    same_x = math.isclose(start_pose.x, end_pose.x, abs_tol=1e-9)
    same_y = math.isclose(start_pose.y, end_pose.y, abs_tol=1e-9)
    same_z = math.isclose(start_pose.z, end_pose.z, abs_tol=1e-9)
    if same_x and same_y and same_z:
        return "hold"
    if same_x and same_y:
        return "lift_z" if end_pose.z > start_pose.z else "descend_z"
    if same_z:
        return "traverse_xy"
    return "move_xyz"


def _motion_segment(
    *,
    start_pose: MotionPose,
    end_pose: MotionPose,
    feed_rate: float = _DEFAULT_FEED_RATE,
) -> MotionSegmentPlan:
    distance_mm = _distance_mm(start_pose, end_pose)
    return MotionSegmentPlan(
        phase=_segment_phase(start_pose, end_pose),
        start_pose=start_pose,
        end_pose=end_pose,
        feed_rate=feed_rate,
        distance_mm=distance_mm,
        real_duration_s=_duration_s(distance_mm, feed_rate),
    )


def _resolve_gantry_target(x: float, y: float, z: float, instrument: Any) -> MotionPose:
    return MotionPose(
        x=float(x) - float(instrument.offset_x),
        y=float(y) - float(instrument.offset_y),
        z=float(z) - float(instrument.depth),
    )


def _resolve_instrument_tip_pose(gantry_pose: Any, instrument: Any) -> MotionPose:
    pose = _coerce_motion_pose(gantry_pose)
    return MotionPose(
        x=pose.x + float(instrument.offset_x),
        y=pose.y + float(instrument.offset_y),
        z=pose.z + float(instrument.depth),
    )


class _TracingGantry:
    """Minimal gantry used during export playback."""

    def __init__(self, initial_pose: MotionPose) -> None:
        self._pose = initial_pose

    def move_to(self, x: float, y: float, z: float) -> None:
        self._pose = MotionPose(x=float(x), y=float(y), z=float(z))

    def get_coordinates(self) -> dict[str, float]:
        return self._pose.to_dict()

    def home(self) -> None:
        self._pose = MotionPose(x=0.0, y=0.0, z=self._pose.z)

    def zero_coordinates(self) -> None:
        self._pose = MotionPose(x=0.0, y=0.0, z=self._pose.z)

    def set_serial_timeout(self, _seconds: float) -> None:
        return None


def _iter_actionable_named_target_ids(labware: Any) -> list[str]:
    if isinstance(labware, WellPlate):
        return sorted(labware.wells)
    if isinstance(labware, TipRack):
        return sorted(labware.tips)
    if isinstance(labware, HolderLabware):
        target_ids: list[str] = []
        for child_name, child_labware in sorted(labware.contained_labware.items()):
            target_ids.append(child_name)
            for child_target_id in _iter_actionable_named_target_ids(child_labware):
                target_ids.append(f"{child_name}.{child_target_id}")
        return target_ids
    return []


class TracingBoard(Board):
    """Board that records atomic motion segments instead of sending G-code."""

    def __init__(
        self,
        *,
        gantry: _TracingGantry,
        instruments: dict[str, Any],
        timeline: list[dict[str, Any]],
        deck: Deck | None = None,
        feed_rate: float = _DEFAULT_FEED_RATE,
    ) -> None:
        super().__init__(gantry=gantry, instruments=instruments)
        self.timeline = timeline
        self.feed_rate = feed_rate
        self.deck = deck
        self._active_step: ProtocolStep | None = None
        self._last_target_label: str | None = None
        self._coordinate_lookup = self._build_coordinate_lookup(deck)
        self._xy_lookup = self._build_xy_lookup(deck)

    def set_active_step(self, step: ProtocolStep | None) -> None:
        self._active_step = step

    def append_action_event(
        self,
        *,
        kind: str,
        duration_s: float = 0.0,
        instrument_id: str | None = None,
        target_label: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._active_step is None:
            raise RuntimeError("TracingBoard step context must be set before recording events.")
        self.timeline.append(
            {
                "type": "action",
                "step_index": self._active_step.index,
                "command": self._active_step.command_name,
                "kind": kind,
                "instrument_id": instrument_id,
                "target_label": target_label,
                "duration_s": duration_s,
                "payload": payload or {},
            }
        )

    def append_dwell_event(self, *, duration_s: float, label: str) -> None:
        if self._active_step is None:
            raise RuntimeError("TracingBoard step context must be set before recording events.")
        self.timeline.append(
            {
                "type": "dwell",
                "step_index": self._active_step.index,
                "command": self._active_step.command_name,
                "duration_s": duration_s,
                "label": label,
            }
        )

    @property
    def last_target_label(self) -> str | None:
        return self._last_target_label

    def _build_coordinate_lookup(self, deck: Deck | None) -> dict[tuple[float, float, float], str]:
        if deck is None:
            return {}

        lookup: dict[tuple[float, float, float], str] = {}
        for deck_key, labware in deck.labware.items():
            lookup[_coord_key(labware.get_default_target())] = deck_key
            for target_id in _iter_actionable_named_target_ids(labware):
                try:
                    label = f"{deck_key}.{target_id}"
                    lookup[_coord_key(labware.get_named_target(target_id))] = label
                except KeyError:
                    continue
        return lookup

    def _build_xy_lookup(self, deck: Deck | None) -> dict[tuple[float, float], str]:
        if deck is None:
            return {}

        lookup: dict[tuple[float, float], str] = {}
        for deck_key, labware in deck.labware.items():
            default_target = _coerce_motion_pose(labware.get_default_target())
            lookup[(round(default_target.x, 6), round(default_target.y, 6))] = deck_key
            for target_id in _iter_actionable_named_target_ids(labware):
                try:
                    target = _coerce_motion_pose(labware.get_named_target(target_id))
                except KeyError:
                    continue
                lookup[(round(target.x, 6), round(target.y, 6))] = f"{deck_key}.{target_id}"
        return lookup

    def _target_label_for_position(self, position: Any) -> str:
        if self._active_step is not None and "position" in self._active_step.args:
            raw_position = self._active_step.args["position"]
            if isinstance(raw_position, str):
                return raw_position

        lookup_key = _coord_key(position)
        if lookup_key in self._coordinate_lookup:
            return self._coordinate_lookup[lookup_key]
        pose = _coerce_motion_pose(position)
        xy_key = (round(pose.x, 6), round(pose.y, 6))
        if xy_key in self._xy_lookup:
            return self._xy_lookup[xy_key]
        return _format_target_label(position)

    def _current_gantry_pose(self) -> MotionPose:
        return _coerce_motion_pose(self.gantry.get_coordinates())

    def _current_tip_position(self, instrument: Any) -> MotionPose:
        return _resolve_instrument_tip_pose(self._current_gantry_pose(), instrument)

    def _record_gantry_move(
        self,
        *,
        instrument_id: str,
        instrument: Any,
        end_pose: MotionPose,
        target_label: str,
    ) -> None:
        if self._active_step is None:
            raise RuntimeError("TracingBoard step context must be set before moves.")
        start_pose = self._current_gantry_pose()
        if _coord_key(start_pose) == _coord_key(end_pose):
            return
        segment = _motion_segment(
            start_pose=start_pose,
            end_pose=end_pose,
            feed_rate=self.feed_rate,
        )
        self.timeline.append(
            _motion_event_from_segment(
                step=self._active_step,
                instrument_id=instrument_id,
                instrument=instrument,
                target_label=target_label,
                segment=segment,
            )
        )
        self.gantry.move_to(end_pose.x, end_pose.y, end_pose.z)

    def move(
        self,
        instrument: str | Any,
        position: Any,
    ) -> None:
        instr = self._resolve_instrument(instrument)
        self._require_xyz_calibrated_instrument(instr)
        instrument_id = instrument if isinstance(instrument, str) else instr.name
        x, y, z = self._resolve_position(position)
        gantry_target = _resolve_gantry_target(x, y, z, instr)
        target_label = self._target_label_for_position(position)
        self._record_gantry_move(
            instrument_id=instrument_id,
            instrument=instr,
            end_pose=gantry_target,
            target_label=target_label,
        )
        self._last_target_label = target_label

    def move_to_labware(
        self,
        instrument: str | Any,
        labware: Any,
    ) -> None:
        instr = self._resolve_instrument(instrument)
        self._require_xyz_calibrated_instrument(instr)
        instrument_id = instrument if isinstance(instrument, str) else instr.name
        x, y, z = self._resolve_position(labware)
        target_label = self._target_label_for_position(labware)
        approach_z = z + float(instr.safe_approach_height)
        current_tip = self._current_tip_position(instr)

        if current_tip.z < approach_z - _Z_TOLERANCE_MM:
            lift_pose = _resolve_gantry_target(current_tip.x, current_tip.y, approach_z, instr)
            self._record_gantry_move(
                instrument_id=instrument_id,
                instrument=instr,
                end_pose=lift_pose,
                target_label=target_label,
            )

        approach_pose = _resolve_gantry_target(x, y, approach_z, instr)
        self._record_gantry_move(
            instrument_id=instrument_id,
            instrument=instr,
            end_pose=approach_pose,
            target_label=target_label,
        )
        self._last_target_label = target_label


def _motion_event_from_segment(
    *,
    step: ProtocolStep,
    instrument_id: str,
    instrument: Any,
    target_label: str,
    segment: MotionSegmentPlan,
) -> dict[str, Any]:
    start_tip = _resolve_instrument_tip_pose(segment.start_pose, instrument)
    end_tip = _resolve_instrument_tip_pose(segment.end_pose, instrument)
    return {
        "type": "motion",
        "step_index": step.index,
        "command": step.command_name,
        "phase": segment.phase,
        "instrument_id": instrument_id,
        "target_label": target_label,
        "start_gantry_pose": segment.start_pose.to_dict(),
        "end_gantry_pose": segment.end_pose.to_dict(),
        "start_tip_pose": start_tip.to_dict(),
        "end_tip_pose": end_tip.to_dict(),
        "feed_rate": segment.feed_rate,
        "distance_mm": segment.distance_mm,
        "real_duration_s": segment.real_duration_s,
        "display_duration_s": max(segment.real_duration_s, 0.05),
    }


def _result_payload(result: Any) -> dict[str, Any]:
    payload = {"result_type": type(result).__name__}
    if hasattr(result, "is_valid"):
        payload["is_valid"] = bool(getattr(result, "is_valid"))
    return payload


def _install_action_wrappers(protocol: Protocol, board: TracingBoard) -> None:
    wrapped_methods: set[tuple[str, str]] = set()
    for step in protocol.steps:
        if step.command_name != "scan":
            continue

        instrument_id = step.args["instrument"]
        method_name = step.args["method"]
        wrapped_key = (instrument_id, method_name)
        if wrapped_key in wrapped_methods:
            continue

        instrument = board.instruments[instrument_id]
        original_method = getattr(instrument, method_name)

        def _wrapped_method(
            *args,
            __orig=original_method,
            __instrument_id=instrument_id,
            __method_name=method_name,
            **kwargs,
        ):
            result = __orig(*args, **kwargs)
            board.append_action_event(
                kind=__method_name,
                instrument_id=__instrument_id,
                target_label=board.last_target_label,
                payload=_result_payload(result),
            )
            return result

        setattr(instrument, method_name, _wrapped_method)
        wrapped_methods.add(wrapped_key)


def _expand_load_names(raw: dict[str, Any]) -> dict[str, Any]:
    labware = raw.get("labware")
    if not isinstance(labware, dict):
        return raw

    expanded_entries: dict[str, Any] = {}
    for deck_key, entry in labware.items():
        if not isinstance(entry, dict) or "load_name" not in entry:
            expanded_entries[deck_key] = entry
            continue

        load_name = entry["load_name"]
        base = dict(load_definition_config(load_name))
        merged = dict(base)
        for key, value in entry.items():
            if key == "load_name":
                continue
            merged[key] = value
        if "name" not in merged:
            merged["name"] = deck_key
        expanded_entries[deck_key] = merged

    expanded = dict(raw)
    expanded["labware"] = expanded_entries
    return expanded


@dataclass(frozen=True)
class _PlateOrientation:
    col_delta_x: float
    col_delta_y: float
    row_delta_x: float
    row_delta_y: float


def _resolve_plate_orientation(entry: Any) -> _PlateOrientation:
    a1 = entry.a1_point
    a2 = entry.calibration.a2
    same_x = abs(a1.x - a2.x) < 1e-9
    same_y = abs(a1.y - a2.y) < 1e-9

    if same_y:
        return _PlateOrientation(
            col_delta_x=a2.x - a1.x,
            col_delta_y=0.0,
            row_delta_x=0.0,
            row_delta_y=entry.y_offset_mm,
        )

    if same_x:
        return _PlateOrientation(
            col_delta_x=0.0,
            col_delta_y=a2.y - a1.y,
            row_delta_x=entry.x_offset_mm,
            row_delta_y=0.0,
        )

    raise ValueError("Calibration must be axis-aligned (same x or same y).")


def _resolve_definition_asset_path(load_name: str | None) -> Path | None:
    if not load_name:
        return None
    entry = (load_registry().get("labware") or {}).get(load_name)
    if not isinstance(entry, dict):
        return None
    config_path = Path(definition_registry.__file__).resolve().parent / entry["config"]
    definition_dir = config_path.parent
    preferred = definition_dir / f"{config_path.stem}.glb"
    if preferred.exists():
        return preferred
    matches = sorted(definition_dir.glob("*.glb"))
    return matches[0] if matches else None


def _select_render_kind(
    *,
    labware: Any,
    load_name: str | None,
) -> tuple[str, Path | None]:
    asset_source = _resolve_definition_asset_path(load_name)
    if asset_source is not None:
        return ("asset", asset_source)
    if isinstance(labware, WellPlate):
        return ("well_plate", None)
    if isinstance(labware, TipRack):
        return ("tip_rack", None)
    if isinstance(labware, Vial):
        return ("vial", None)
    if isinstance(labware, Wall):
        return ("wall", None)
    return ("bounding_box", None)


def _point_payloads(points: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": point_id, "position": _coord_dict(coord)}
        for point_id, coord in sorted(points.items())
    ]


def _dimensions_payload(labware: Any) -> dict[str, float | None]:
    geometry = getattr(labware, "geometry", None)
    if geometry is None:
        return {"length_mm": None, "width_mm": None, "height_mm": None}
    return {
        "length_mm": getattr(geometry, "length_mm", None),
        "width_mm": getattr(geometry, "width_mm", None),
        "height_mm": getattr(geometry, "height_mm", None),
    }


def _pose_center(poses: list[dict[str, float]]) -> dict[str, float]:
    xs = [pose["x"] for pose in poses]
    ys = [pose["y"] for pose in poses]
    zs = [pose["z"] for pose in poses]
    return {
        "x": (min(xs) + max(xs)) / 2,
        "y": (min(ys) + max(ys)) / 2,
        "z": (min(zs) + max(zs)) / 2,
    }


def _placement_anchor_payload(labware: Any) -> dict[str, float] | None:
    if isinstance(labware, (TipRack, HolderLabware)):
        return _coord_dict(labware.location)
    if isinstance(labware, Vial):
        return {
            "x": float(labware.location.x),
            "y": float(labware.location.y),
            "z": float(labware.location.z) - float(labware.height_mm),
        }
    return None


def _named_targets_payload(labware: Any) -> list[dict[str, Any]]:
    return _point_payloads(
        {
            target_id: labware.get_named_target(target_id)
            for target_id in _iter_actionable_named_target_ids(labware)
        }
    )


def _validation_points_payload(labware: Any) -> list[dict[str, Any]]:
    return _point_payloads(labware.iter_validation_points())


def _twin_anchor_payload(
    *,
    labware: Any,
    dimensions: dict[str, float | None],
    placement_anchor: dict[str, float] | None,
    default_target: dict[str, float],
    named_targets: list[dict[str, Any]],
) -> dict[str, float]:
    height_mm = float(dimensions["height_mm"] or 0.0)
    if isinstance(labware, (WellPlate, TipRack)):
        top_points = [point["position"] for point in named_targets] or [default_target]
        center = _pose_center(top_points)
        center["z"] = center["z"] - height_mm / 2
        return center
    if isinstance(labware, Vial):
        return {
            "x": default_target["x"],
            "y": default_target["y"],
            "z": default_target["z"] - height_mm / 2,
        }
    if isinstance(labware, TipDisposal) and placement_anchor is not None:
        return {
            "x": placement_anchor["x"] + float(dimensions["length_mm"] or 0.0) / 2,
            "y": placement_anchor["y"] + float(dimensions["width_mm"] or 0.0) / 2,
            "z": placement_anchor["z"] + height_mm / 2,
        }
    if isinstance(labware, (VialHolder, WellPlateHolder)):
        child_targets = [
            _coord_dict(child.get_default_target())
            for child in labware.contained_labware.values()
        ]
        if child_targets and placement_anchor is not None:
            center = _pose_center(child_targets)
            center["z"] = placement_anchor["z"] + height_mm / 2
            return center
    if isinstance(labware, Wall):
        return {
            "x": (labware.corner_1.x + labware.corner_2.x) / 2,
            "y": (labware.corner_1.y + labware.corner_2.y) / 2,
            "z": (labware.corner_1.z + labware.corner_2.z) / 2,
        }
    if placement_anchor is not None and height_mm > 0:
        return {
            "x": placement_anchor["x"],
            "y": placement_anchor["y"],
            "z": placement_anchor["z"] + height_mm / 2,
        }
    return dict(default_target)


def _well_plate_render_meta(
    entry: WellPlateYamlEntry | NestedWellPlateYamlEntry,
    labware: WellPlate,
) -> dict[str, Any]:
    orientation = _resolve_plate_orientation(entry)
    return {
        "rows": entry.rows,
        "columns": entry.columns,
        "a1": _coord_dict(labware.get_location("A1")),
        "a2": _coord_dict(labware.get_location("A2")),
        "column_vector": {
            "x": orientation.col_delta_x,
            "y": orientation.col_delta_y,
        },
        "row_vector": {
            "x": orientation.row_delta_x,
            "y": orientation.row_delta_y,
        },
        "x_offset_mm": entry.x_offset_mm,
        "y_offset_mm": entry.y_offset_mm,
    }


def _tip_rack_render_meta(
    entry: TipRackYamlEntry,
    labware: TipRack,
) -> dict[str, Any]:
    orientation = _resolve_plate_orientation(entry)
    return {
        "rows": entry.rows,
        "columns": entry.columns,
        "a1": _coord_dict(labware.get_location("A1")),
        "a2": _coord_dict(labware.get_location("A2")),
        "column_vector": {
            "x": orientation.col_delta_x,
            "y": orientation.col_delta_y,
        },
        "row_vector": {
            "x": orientation.row_delta_x,
            "y": orientation.row_delta_y,
        },
        "x_offset_mm": entry.x_offset_mm,
        "y_offset_mm": entry.y_offset_mm,
        "z_pickup": entry.z_pickup,
        "z_drop": entry.z_drop,
    }


def _scene_item_payload(
    *,
    item_id: str,
    labware: Any,
    entry: Any,
    load_name: str | None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    render_kind, asset_source = _select_render_kind(labware=labware, load_name=load_name)
    dimensions = _dimensions_payload(labware)
    placement_anchor = _placement_anchor_payload(labware)
    default_target = _coord_dict(labware.get_default_target())
    named_targets = _named_targets_payload(labware)
    validation_points = _validation_points_payload(labware)
    item = {
        "id": item_id,
        "parent_id": parent_id,
        "type": getattr(entry, "type", labware.__class__.__name__.lower()),
        "name": getattr(labware, "name", item_id),
        "model_name": getattr(labware, "model_name", ""),
        "render_kind": render_kind,
        "asset_path": None,
        "asset_source_path": str(asset_source) if asset_source is not None else None,
        "placement_anchor": placement_anchor,
        "default_target": default_target,
        "twin_anchor": _twin_anchor_payload(
            labware=labware,
            dimensions=dimensions,
            placement_anchor=placement_anchor,
            default_target=default_target,
            named_targets=named_targets,
        ),
        "dimensions": dimensions,
        "named_targets": named_targets,
        "validation_points": validation_points,
        "render_meta": {},
    }
    if isinstance(entry, (WellPlateYamlEntry, NestedWellPlateYamlEntry)):
        item["render_meta"] = _well_plate_render_meta(entry, labware)
    elif isinstance(entry, TipRackYamlEntry):
        item["render_meta"] = _tip_rack_render_meta(entry, labware)
    elif isinstance(entry, (VialYamlEntry, NestedVialYamlEntry)):
        item["render_meta"] = {
            "diameter_mm": getattr(entry, "diameter_mm", None),
            "height_mm": getattr(entry, "height_mm", None),
        }
    elif isinstance(entry, (WellPlateHolderYamlEntry, VialHolderYamlEntry)):
        item["render_meta"] = {
            "labware_support_height_mm": getattr(labware, "labware_support_height_mm", None),
            "labware_seat_height_from_bottom_mm": getattr(
                labware,
                "labware_seat_height_from_bottom_mm",
                None,
            ),
        }
    return item


def _flatten_scene_items(
    *,
    deck: Deck,
    resolved_entries: dict[str, Any],
    original_entries: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for deck_key, labware in deck.labware.items():
        resolved_entry = resolved_entries[deck_key]
        original_entry = original_entries.get(deck_key, {})
        load_name = original_entry.get("load_name")
        items.append(
            _scene_item_payload(
                item_id=deck_key,
                labware=labware,
                entry=resolved_entry,
                load_name=load_name,
            )
        )
        if isinstance(labware, WellPlateHolder) and resolved_entry.well_plate is not None:
            child_labware = labware.contained_labware.get("plate")
            if child_labware is not None:
                items.append(
                    _scene_item_payload(
                        item_id=f"{deck_key}.plate",
                        labware=child_labware,
                        entry=resolved_entry.well_plate,
                        load_name=None,
                        parent_id=deck_key,
                    )
                )
        if isinstance(labware, VialHolder):
            for vial_key, vial_entry in resolved_entry.vials.items():
                child_labware = labware.contained_labware.get(vial_key)
                if child_labware is None:
                    continue
                items.append(
                    _scene_item_payload(
                        item_id=f"{deck_key}.{vial_key}",
                        labware=child_labware,
                        entry=vial_entry,
                        load_name=None,
                        parent_id=deck_key,
                    )
                )
    return items


def _copy_scene_assets(scene_items: list[dict[str, Any]], *, output_path: Path | None) -> None:
    if output_path is None:
        for item in scene_items:
            item["asset_path"] = item.pop("asset_source_path", None)
        return

    asset_dir = output_path.parent / "assets"
    public_prefix = Path("assets")
    try:
        public_root = next(parent for parent in output_path.parents if parent.name == "public")
        relative_dir = output_path.parent.relative_to(public_root)
        public_prefix = relative_dir / "assets"
    except StopIteration:
        pass
    except ValueError:
        pass

    copied: dict[Path, str] = {}
    for item in scene_items:
        source_path_value = item.pop("asset_source_path", None)
        if source_path_value is None:
            item["asset_path"] = None
            continue
        source_path = Path(source_path_value)
        if source_path not in copied:
            asset_dir.mkdir(parents=True, exist_ok=True)
            destination = asset_dir / source_path.name
            shutil.copy2(source_path, destination)
            copied[source_path] = "/" + str(public_prefix / destination.name)
        item["asset_path"] = copied[source_path]


def _build_scene(
    *,
    gantry_config: GantryConfig,
    deck: Deck,
    board_schema: BoardYamlSchema,
    board: Board,
    deck_original: dict[str, Any],
    deck_resolved_schema: DeckYamlSchema,
    output_path: Path | None,
) -> dict[str, Any]:
    scene_items = _flatten_scene_items(
        deck=deck,
        resolved_entries=deck_resolved_schema.labware,
        original_entries=deck_original.get("labware", {}),
    )
    _copy_scene_assets(scene_items, output_path=output_path)
    initial_gantry_pose = MotionPose(
        x=0.0,
        y=0.0,
        z=float(gantry_config.working_volume.z_max),
    )
    instruments = []
    for instrument_id, entry in board_schema.instruments.items():
        instrument = board.instruments[instrument_id]
        instruments.append(
            {
                "id": instrument_id,
                "type": entry.type,
                "vendor": entry.vendor,
                "offset_x": instrument.offset_x,
                "offset_y": instrument.offset_y,
                "depth": instrument.depth,
                "measurement_height": instrument.measurement_height,
                "safe_approach_height": instrument.safe_approach_height,
                "initial_tip_pose": _resolve_instrument_tip_pose(
                    initial_gantry_pose,
                    instrument,
                ).to_dict(),
            }
        )

    return {
        "contract_version": "cubos-deck-base-z0-v2",
        "gantry": {
            "working_volume": {
                "x_min": gantry_config.working_volume.x_min,
                "x_max": gantry_config.working_volume.x_max,
                "y_min": gantry_config.working_volume.y_min,
                "y_max": gantry_config.working_volume.y_max,
                "z_min": gantry_config.working_volume.z_min,
                "z_max": gantry_config.working_volume.z_max,
            },
            "homing_strategy": gantry_config.homing_strategy.value,
            "y_axis_motion": gantry_config.y_axis_motion.value,
            "initial_gantry_pose": initial_gantry_pose.to_dict(),
            "total_z_height": gantry_config.total_z_height,
        },
        "deck": scene_items,
        "instruments": instruments,
    }


def _ensure_supported_protocol(protocol: Protocol) -> None:
    unsupported = sorted(
        {
            step.command_name
            for step in protocol.steps
            if step.command_name not in _SUPPORTED_PHASE_ONE_COMMANDS
        }
    )
    if unsupported:
        raise NotImplementedError(
            "Phase 1 exporter currently supports only move and scan commands. "
            f"Unsupported commands: {', '.join(unsupported)}"
        )


def _run_traced_protocol(protocol: Protocol, context: ProtocolContext, board: TracingBoard) -> None:
    _install_action_wrappers(protocol, board)
    board.connect_instruments()
    try:
        for step in protocol.steps:
            board.set_active_step(step)
            step.execute(context)
        board.set_active_step(None)
    finally:
        board.disconnect_instruments()


def export_bundle(
    *,
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    output_path: str | Path | None = None,
    skip_validation: bool = False,
) -> dict[str, Any]:
    """Build a digital twin bundle from CubOS config files."""

    resolved_output_path = Path(output_path) if output_path is not None else None
    gantry_config = load_gantry_from_yaml_safe(gantry_path)
    deck = load_deck_from_yaml_safe(deck_path)

    initial_gantry_pose = MotionPose(
        x=0.0,
        y=0.0,
        z=float(gantry_config.working_volume.z_max),
    )
    tracing_gantry = _TracingGantry(initial_pose=initial_gantry_pose)
    loaded_board = load_board_from_yaml_safe(board_path, tracing_gantry, mock_mode=True)
    timeline: list[dict[str, Any]] = []
    tracing_board = TracingBoard(
        gantry=tracing_gantry,
        instruments=loaded_board.instruments,
        timeline=timeline,
        deck=deck,
    )
    protocol = load_protocol_from_yaml_safe(protocol_path)
    _ensure_supported_protocol(protocol)

    violations = validate_deck_positions(gantry_config, deck)
    violations.extend(validate_gantry_positions(gantry_config, deck, tracing_board))
    if violations and not skip_validation:
        raise SetupValidationError(violations)

    board_schema = BoardYamlSchema.model_validate(_load_yaml(board_path))
    deck_original = _load_yaml(deck_path)
    deck_resolved_schema = DeckYamlSchema.model_validate(_expand_load_names(deck_original))

    context = ProtocolContext(
        board=tracing_board,
        deck=deck,
        positions=protocol.positions,
        gantry=gantry_config,
    )
    _run_traced_protocol(protocol, context, tracing_board)

    bundle = {
        "scene": _build_scene(
            gantry_config=gantry_config,
            deck=deck,
            board_schema=board_schema,
            board=tracing_board,
            deck_original=deck_original,
            deck_resolved_schema=deck_resolved_schema,
            output_path=resolved_output_path,
        ),
        "timeline": timeline,
        "summary": {
            "step_count": len(protocol.steps),
            "timeline_event_count": len(timeline),
            "total_display_duration_s": sum(_event_base_duration(event) for event in timeline),
            "validation_skipped": skip_validation,
            "validation_violation_count": len(violations),
        },
    }
    return bundle


def export_bundle_to_path(
    *,
    gantry_path: str | Path,
    deck_path: str | Path,
    board_path: str | Path,
    protocol_path: str | Path,
    output_path: str | Path,
    skip_validation: bool = False,
) -> dict[str, Any]:
    """Build and write a digital twin bundle to disk."""

    resolved_output_path = Path(output_path)
    bundle = export_bundle(
        gantry_path=gantry_path,
        deck_path=deck_path,
        board_path=board_path,
        protocol_path=protocol_path,
        output_path=resolved_output_path,
        skip_validation=skip_validation,
    )
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle
