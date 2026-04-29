export type Point3D = {
  x: number;
  y: number;
  z: number;
};

export type Aabb = {
  label: string;
  kind: string;
  min: Point3D;
  max: Point3D;
  size: Point3D;
  center: Point3D;
};

export type LabwareItem = {
  key: string;
  parentKey: string | null;
  name: string;
  kind: string;
  modelName: string;
  anchor: Point3D;
  geometry: Record<string, number | null>;
  aabb: Aabb | null;
  positions: Record<string, Point3D>;
  wells?: Array<{ id: string; center: Point3D }>;
  tips?: Array<{ id: string; center: Point3D; present: boolean }>;
  children: LabwareItem[];
};

export type Instrument = {
  name: string;
  type: string;
  vendor: string | null;
  offset: Point3D;
  depth: number;
  safeApproachHeight: number;
  measurementHeight: number;
};

export type MotionPoint = {
  index: number;
  stepIndex: number;
  command: string;
  phase: string;
  targetRef: string;
  instrument: string;
  tool: Point3D;
  gantry: Point3D;
  envelope: Aabb;
};

export type TimelineStep = {
  index: number;
  command: string;
  args: Record<string, unknown>;
  pathStart: number;
  pathEnd: number;
};

export type TwinWarning = {
  severity: "warning" | "error";
  type: string;
  stepIndex: number;
  pathIndex: number;
  instrument: string;
  targetRef: string;
  object: string;
  distanceMm: number;
  message: string;
};

export type DigitalTwin = {
  schemaVersion: string;
  generatedAt: string;
  source: Record<string, string | null>;
  coordinateSystem: {
    frame: string;
    origin: string;
    axes: Record<string, string>;
    units: string;
  };
  gantry: {
    workingVolume: {
      x_min: number;
      x_max: number;
      y_min: number;
      y_max: number;
      z_min: number;
      z_max: number;
    };
    homePosition: Point3D;
    instruments: Instrument[];
  };
  deck: { labware: LabwareItem[] };
  protocol: {
    positions: Record<string, Point3D>;
    timeline: TimelineStep[];
  };
  motion: {
    timeline: TimelineStep[];
    segments: unknown[];
    path: MotionPoint[];
  };
  warnings: TwinWarning[];
};
