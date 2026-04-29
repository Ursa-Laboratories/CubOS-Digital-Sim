import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App, { cubosToThree } from "./App";
import type { DigitalTwin } from "./types";

const twin: DigitalTwin = {
  schemaVersion: "digital-twin.v1",
  generatedAt: "2026-01-01T00:00:00Z",
  source: {},
  coordinateSystem: {
    frame: "CubOS deck frame",
    origin: "front-left-bottom reachable work volume",
    axes: { "+x": "right", "+y": "away/back", "+z": "up" },
    units: "millimeters",
  },
  gantry: {
    workingVolume: { x_min: 0, x_max: 100, y_min: 0, y_max: 100, z_min: 0, z_max: 50 },
    homePosition: { x: 100, y: 100, z: 50 },
    instruments: [{ name: "probe", type: "probe", vendor: null, offset: { x: 0, y: 0, z: 0 }, depth: 10, safeApproachHeight: 20, measurementHeight: 5 }],
  },
  deck: { labware: [] },
  protocol: { positions: {}, timeline: [{ index: 0, command: "home", args: {}, pathStart: 0, pathEnd: 0 }] },
  motion: {
    timeline: [],
    segments: [],
    path: [{
      index: 0,
      stepIndex: 0,
      command: "home",
      phase: "home",
      targetRef: "home",
      instrument: "probe",
      tool: { x: 100, y: 100, z: 40 },
      gantry: { x: 100, y: 100, z: 50 },
      envelope: {
        label: "probe",
        kind: "instrument_envelope",
        min: { x: 91, y: 91, z: 40 },
        max: { x: 109, y: 109, z: 60 },
        size: { x: 18, y: 18, z: 20 },
        center: { x: 100, y: 100, z: 50 },
      },
    }],
  },
  warnings: [],
};

describe("viewer", () => {
  it("maps CubOS +Z to Three.js Y and +Y to negative Z", () => {
    expect(cubosToThree({ x: 1, y: 2, z: 3 })).toEqual([1, 3, -2]);
  });

  it("renders timeline and pose controls", () => {
    render(<App initialTwin={twin} />);
    expect(screen.getByText("CubOS Digital Twin")).toBeInTheDocument();
    expect(screen.getAllByText("home").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Motion path sample")).toBeInTheDocument();
  });
});
