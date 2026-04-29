import { OrbitControls, Text } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import type { Aabb, DigitalTwin, LabwareItem, MotionPoint, Point3D } from "./types";
import "./index.css";

const EXAMPLE_URL = "/examples/sterling-vial-scan.json";

export function cubosToThree(point: Point3D): [number, number, number] {
  return [point.x, point.z, -point.y];
}

function aabbCenterSize(aabb: Aabb): { center: [number, number, number]; size: [number, number, number] } {
  return {
    center: cubosToThree(aabb.center),
    size: [aabb.size.x, aabb.size.z, aabb.size.y],
  };
}

function flattenLabware(items: LabwareItem[]): LabwareItem[] {
  return items.flatMap((item) => [item, ...flattenLabware(item.children ?? [])]);
}

function Volume({ twin }: { twin: DigitalTwin }) {
  const v = twin.gantry.workingVolume;
  const center = cubosToThree({
    x: (v.x_min + v.x_max) / 2,
    y: (v.y_min + v.y_max) / 2,
    z: (v.z_min + v.z_max) / 2,
  });
  const size: [number, number, number] = [v.x_max - v.x_min, v.z_max - v.z_min, v.y_max - v.y_min];
  return (
    <group>
      <mesh position={center}>
        <boxGeometry args={size} />
        <meshBasicMaterial color="#96a3b7" wireframe transparent opacity={0.42} />
      </mesh>
      <line>
        <bufferGeometry
          attach="geometry"
          attributes={{
            position: new THREE.BufferAttribute(new Float32Array([0, 0, 0, 80, 0, 0]), 3),
          }}
        />
        <lineBasicMaterial color="#d13f31" />
      </line>
      <line>
        <bufferGeometry
          attach="geometry"
          attributes={{
            position: new THREE.BufferAttribute(new Float32Array([0, 0, 0, 0, 0, -80]), 3),
          }}
        />
        <lineBasicMaterial color="#247a3d" />
      </line>
      <line>
        <bufferGeometry
          attach="geometry"
          attributes={{
            position: new THREE.BufferAttribute(new Float32Array([0, 0, 0, 0, 80, 0]), 3),
          }}
        />
        <lineBasicMaterial color="#2d5fd7" />
      </line>
      <Text position={[88, 0, 0]} fontSize={9} color="#d13f31">+X</Text>
      <Text position={[0, 0, -88]} fontSize={9} color="#247a3d">+Y</Text>
      <Text position={[0, 88, 0]} fontSize={9} color="#2d5fd7">+Z</Text>
    </group>
  );
}

function LabwareMesh({ item }: { item: LabwareItem }) {
  const color = item.kind.includes("vial") ? "#bf7a30" : item.kind.includes("plate") ? "#4b87b9" : "#6f7c48";
  return (
    <group>
      {item.aabb ? (
        <mesh position={aabbCenterSize(item.aabb).center}>
          <boxGeometry args={aabbCenterSize(item.aabb).size} />
          <meshStandardMaterial color={color} transparent opacity={0.32} />
        </mesh>
      ) : null}
      {item.wells?.map((well) => (
        <mesh key={well.id} position={cubosToThree(well.center)}>
          <cylinderGeometry args={[2.1, 2.1, 1.5, 16]} />
          <meshStandardMaterial color="#1d4f78" />
        </mesh>
      ))}
      {item.tips?.map((tip) => (
        <mesh key={tip.id} position={cubosToThree(tip.center)}>
          <cylinderGeometry args={[1.8, 1.8, 5, 10]} />
          <meshStandardMaterial color={tip.present ? "#75905b" : "#858585"} />
        </mesh>
      ))}
    </group>
  );
}

function MotionPath({ path }: { path: MotionPoint[] }) {
  const positions = useMemo(() => new Float32Array(path.flatMap((point) => cubosToThree(point.tool))), [path]);
  return (
    <line>
      <bufferGeometry attach="geometry" attributes={{ position: new THREE.BufferAttribute(positions, 3) }} />
      <lineBasicMaterial color="#101827" />
    </line>
  );
}

function Gantry({ twin, point }: { twin: DigitalTwin; point: MotionPoint }) {
  const volume = twin.gantry.workingVolume;
  const bridgePos = cubosToThree({ x: (volume.x_min + volume.x_max) / 2, y: point.gantry.y, z: point.gantry.z });
  const carriagePos = cubosToThree(point.gantry);
  const toolPos = cubosToThree(point.tool);
  return (
    <group>
      <mesh position={bridgePos}>
        <boxGeometry args={[volume.x_max - volume.x_min, 5, 8]} />
        <meshStandardMaterial color="#3b414d" />
      </mesh>
      <mesh position={carriagePos}>
        <boxGeometry args={[24, 18, 18]} />
        <meshStandardMaterial color="#222a35" />
      </mesh>
      <line>
        <bufferGeometry
          attach="geometry"
          attributes={{ position: new THREE.BufferAttribute(new Float32Array([...carriagePos, ...toolPos]), 3) }}
        />
        <lineBasicMaterial color="#ad2f2f" />
      </line>
      <mesh position={aabbCenterSize(point.envelope).center}>
        <boxGeometry args={aabbCenterSize(point.envelope).size} />
        <meshBasicMaterial color="#d24938" wireframe />
      </mesh>
    </group>
  );
}

function Scene({ twin, current }: { twin: DigitalTwin; current: MotionPoint }) {
  const labware = flattenLabware(twin.deck.labware);
  return (
    <Canvas camera={{ position: [280, 260, 360], fov: 42 }} shadows>
      <color attach="background" args={["#f4f6f8"]} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[200, 350, 150]} intensity={0.9} />
      <Volume twin={twin} />
      {labware.map((item) => <LabwareMesh key={item.key} item={item} />)}
      <MotionPath path={twin.motion.path} />
      <Gantry twin={twin} point={current} />
      <OrbitControls makeDefault target={[150, 35, -145]} />
    </Canvas>
  );
}

function Sidebar({
  twin,
  pathIndex,
  setPathIndex,
}: {
  twin: DigitalTwin;
  pathIndex: number;
  setPathIndex: (value: number) => void;
}) {
  const current = twin.motion.path[pathIndex];
  return (
    <aside className="sidebar">
      <div>
        <h1>CubOS Digital Twin</h1>
        <p>{twin.coordinateSystem.origin}; +X right, +Y back, +Z up.</p>
      </div>
      <label className="slider">
        <span>Path sample {pathIndex + 1} / {twin.motion.path.length}</span>
        <input
          aria-label="Motion path sample"
          type="range"
          min={0}
          max={Math.max(twin.motion.path.length - 1, 0)}
          value={pathIndex}
          onChange={(event) => setPathIndex(Number(event.target.value))}
        />
      </label>
      <section>
        <h2>Current Pose</h2>
        <dl>
          <dt>Step</dt><dd>{current.stepIndex}</dd>
          <dt>Command</dt><dd>{current.command}</dd>
          <dt>Phase</dt><dd>{current.phase}</dd>
          <dt>Target</dt><dd>{current.targetRef}</dd>
          <dt>TCP</dt><dd>{current.tool.x.toFixed(1)}, {current.tool.y.toFixed(1)}, {current.tool.z.toFixed(1)}</dd>
        </dl>
      </section>
      <section>
        <h2>Protocol</h2>
        <ol className="timeline">
          {twin.protocol.timeline.map((step) => (
            <li key={step.index} className={current.stepIndex === step.index ? "active" : ""}>
              <button type="button" onClick={() => setPathIndex(step.pathStart)}>
                <span>{step.index}</span>
                <strong>{step.command}</strong>
              </button>
            </li>
          ))}
        </ol>
      </section>
      <section>
        <h2>Warnings</h2>
        <ul className="warnings">
          {twin.warnings.length === 0 ? <li>No first-pass AABB warnings.</li> : null}
          {twin.warnings.slice(0, 12).map((warning) => (
            <li key={`${warning.stepIndex}-${warning.object}-${warning.type}`}>
              <button type="button" onClick={() => setPathIndex(warning.pathIndex)}>
                <strong>{warning.type}</strong> step {warning.stepIndex}: {warning.object}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

export default function App({ initialTwin }: { initialTwin?: DigitalTwin }) {
  const [twin, setTwin] = useState<DigitalTwin | null>(initialTwin ?? null);
  const [error, setError] = useState<string | null>(null);
  const [pathIndex, setPathIndex] = useState(0);

  useEffect(() => {
    if (initialTwin) return;
    fetch(EXAMPLE_URL)
      .then((response) => {
        if (!response.ok) throw new Error(`Failed to load ${EXAMPLE_URL}: ${response.status}`);
        return response.json();
      })
      .then((data: DigitalTwin) => setTwin(data))
      .catch((reason: Error) => setError(reason.message));
  }, [initialTwin]);

  if (error) return <main className="status">Viewer load failed: {error}</main>;
  if (!twin) return <main className="status">Loading digital twin...</main>;

  const current = twin.motion.path[Math.min(pathIndex, twin.motion.path.length - 1)];
  return (
    <main className="app">
      <Scene twin={twin} current={current} />
      <Sidebar twin={twin} pathIndex={pathIndex} setPathIndex={setPathIndex} />
    </main>
  );
}
