import { describe, expect, it } from "vitest";
import { getDeckYawRadians, getTotalDuration, offsetTipPose, samplePlayback } from "./playback";
import type { TwinBundle } from "../types";

const bundle: TwinBundle = {
  scene: {
    contract_version: "cubos-deck-base-z0-v2",
    gantry: {
      working_volume: {
        x_min: 0,
        x_max: 100,
        y_min: 0,
        y_max: 100,
        z_min: 0,
        z_max: 80,
      },
      homing_strategy: "xy_hard_limits",
      y_axis_motion: "head",
      initial_gantry_pose: { x: 0, y: 0, z: 0 },
      total_z_height: 90,
    },
    deck: [],
    instruments: [
      {
        id: "uvvis",
        type: "uvvis_ccs",
        vendor: "thorlabs",
        offset_x: 5,
        offset_y: -2,
        depth: 7,
        measurement_height: 3,
        safe_approach_height: 3,
        initial_tip_pose: { x: 5, y: -2, z: 7 },
      },
    ],
  },
  timeline: [
    {
      type: "motion",
      step_index: 0,
      command: "move",
      phase: "traverse_xy",
      instrument_id: "uvvis",
      target_label: "plate_1.A1",
      start_gantry_pose: { x: 0, y: 0, z: 0 },
      end_gantry_pose: { x: 10, y: 0, z: 0 },
      start_tip_pose: { x: 5, y: -2, z: 7 },
      end_tip_pose: { x: 15, y: -2, z: 7 },
      feed_rate: 2000,
      distance_mm: 10,
      real_duration_s: 0.3,
      display_duration_s: 0.3,
    },
    {
      type: "motion",
      step_index: 0,
      command: "move",
      phase: "descend_z",
      instrument_id: "uvvis",
      target_label: "plate_1.A1",
      start_gantry_pose: { x: 10, y: 0, z: 0 },
      end_gantry_pose: { x: 10, y: 0, z: 20 },
      start_tip_pose: { x: 15, y: -2, z: 7 },
      end_tip_pose: { x: 15, y: -2, z: 27 },
      feed_rate: 2000,
      distance_mm: 20,
      real_duration_s: 0.6,
      display_duration_s: 0.6,
    },
  ],
  summary: {
    step_count: 1,
    timeline_event_count: 2,
    total_display_duration_s: 0.9,
  },
};

describe("playback helpers", () => {
  it("computes total duration from motion events", () => {
    expect(getTotalDuration(bundle)).toBeCloseTo(0.9);
  });

  it("samples a pose partway through a segment", () => {
    const sample = samplePlayback(bundle, 0.15);
    expect(sample.gantryPose.x).toBeCloseTo(5);
    expect(sample.gantryPose.z).toBeCloseTo(0);
    expect(sample.instrumentTips.uvvis.x).toBeCloseTo(10);
  });

  it("returns the final pose after the timeline completes", () => {
    const sample = samplePlayback(bundle, 10);
    expect(sample.gantryPose).toEqual({ x: 10, y: 0, z: 20 });
    expect(sample.instrumentTips.uvvis).toEqual(offsetTipPose(sample.gantryPose, bundle.scene.instruments[0]));
  });

  it("derives deck yaw from the exported column vector", () => {
    expect(
      getDeckYawRadians({
        id: "plate_1",
        parent_id: null,
        type: "well_plate",
        name: "plate",
        model_name: "sbs",
        render_kind: "well_plate",
        asset_path: null,
        placement_anchor: null,
        default_target: { x: 0, y: 0, z: 0 },
        twin_anchor: { x: 0, y: 0, z: -2.5 },
        dimensions: { length_mm: 10, width_mm: 20, height_mm: 5 },
        named_targets: [],
        validation_points: [],
        render_meta: {
          column_vector: { x: 0, y: 9 },
        },
      }),
    ).toBeCloseTo(-Math.PI / 2);
  });
});
