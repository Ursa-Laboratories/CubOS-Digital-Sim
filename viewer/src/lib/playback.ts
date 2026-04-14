import type {
  MotionEvent,
  Pose,
  SceneDeckItem,
  SceneInstrument,
  TimelineEvent,
  TwinBundle,
  WorkingVolume,
} from "../types";

export const MIN_DISPLAY_DURATION_S = 0.05;

export type PlaybackSample = {
  totalDuration: number;
  currentTime: number;
  gantryPose: Pose;
  instrumentTips: Record<string, Pose>;
  currentEvent: TimelineEvent | null;
  pathPoints: Pose[];
};

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function toWorldPosition(pose: Pose): [number, number, number] {
  return [pose.x, pose.z, -pose.y];
}

export function getDeckYawRadians(item: SceneDeckItem): number {
  const renderMeta = item.render_meta as {
    column_vector?: { x: number; y: number };
  };
  const columnVector = renderMeta.column_vector;
  if (!columnVector) {
    return 0;
  }
  return Math.atan2(-columnVector.y, columnVector.x);
}

export function lerpPose(startPose: Pose, endPose: Pose, progress: number): Pose {
  return {
    x: startPose.x + (endPose.x - startPose.x) * progress,
    y: startPose.y + (endPose.y - startPose.y) * progress,
    z: startPose.z + (endPose.z - startPose.z) * progress,
  };
}

export function offsetTipPose(gantryPose: Pose, instrument: SceneInstrument): Pose {
  return {
    x: gantryPose.x + instrument.offset_x,
    y: gantryPose.y + instrument.offset_y,
    z: gantryPose.z + instrument.depth,
  };
}

export function getEventDuration(event: TimelineEvent): number {
  if (event.type === "motion") {
    return Math.max(event.display_duration_s ?? event.real_duration_s, MIN_DISPLAY_DURATION_S);
  }
  return Math.max(event.duration_s, 0);
}

export function getTotalDuration(bundle: TwinBundle): number {
  return bundle.timeline.reduce((total, event) => total + getEventDuration(event), 0);
}

export function phaseLabel(event: TimelineEvent | null): string {
  if (event === null) {
    return "idle";
  }
  if (event.type === "motion") {
    if (event.phase.startsWith("lift")) {
      return "lift";
    }
    if (event.phase.startsWith("traverse") || event.phase.startsWith("move_x") || event.phase.startsWith("move_y")) {
      return "traverse";
    }
    if (event.phase.endsWith("_z")) {
      return "descend";
    }
    return event.phase;
  }
  if (event.type === "dwell") {
    return "dwell";
  }
  return event.kind;
}

export function samplePlayback(bundle: TwinBundle, timeSeconds: number): PlaybackSample {
  const totalDuration = getTotalDuration(bundle);
  const clampedTime = clamp(timeSeconds, 0, totalDuration);
  let elapsed = 0;
  let gantryPose = bundle.scene.gantry.initial_gantry_pose;
  let currentEvent: TimelineEvent | null = null;
  const pathPoints: Pose[] = [gantryPose];

  for (const event of bundle.timeline) {
    const eventDuration = getEventDuration(event);
    const eventEnd = elapsed + eventDuration;

    if (event.type === "motion") {
      if (clampedTime >= eventEnd) {
        gantryPose = event.end_gantry_pose;
        pathPoints.push(gantryPose);
        elapsed = eventEnd;
        currentEvent = event;
        continue;
      }

      if (clampedTime >= elapsed) {
        const progress = eventDuration === 0 ? 1 : (clampedTime - elapsed) / eventDuration;
        gantryPose = lerpPose(event.start_gantry_pose, event.end_gantry_pose, progress);
        pathPoints.push(gantryPose);
        currentEvent = event;
        break;
      }
    } else if (clampedTime >= elapsed && clampedTime <= eventEnd) {
      currentEvent = event;
      break;
    }

    elapsed = eventEnd;
  }

  const instrumentTips = Object.fromEntries(
    bundle.scene.instruments.map((instrument) => [
      instrument.id,
      offsetTipPose(gantryPose, instrument),
    ]),
  );

  return {
    totalDuration,
    currentTime: clampedTime,
    gantryPose,
    instrumentTips,
    currentEvent,
    pathPoints,
  };
}

export function isPointInsideVolume(point: Pose, volume: WorkingVolume): boolean {
  return (
    point.x >= volume.x_min &&
    point.x <= volume.x_max &&
    point.y >= volume.y_min &&
    point.y <= volume.y_max &&
    point.z >= volume.z_min &&
    point.z <= volume.z_max
  );
}

export function currentStepLabel(event: TimelineEvent | null): string {
  if (event === null) {
    return "No active step";
  }
  return `Step ${event.step_index + 1}: ${event.command}`;
}

export function currentTargetLabel(event: TimelineEvent | null): string {
  if (event === null || event.type === "dwell") {
    return "No target";
  }
  if (event.type === "action") {
    return event.target_label ?? "No target";
  }
  return event.target_label;
}

export function currentMotionEvent(event: TimelineEvent | null): MotionEvent | null {
  return event?.type === "motion" ? event : null;
}
