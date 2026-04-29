from types import SimpleNamespace

from digital_twin.geometry import Point3D
from digital_twin.motion import InstrumentModel, MotionPlanner, interpolate_points


class FakeDeck:
    def resolve(self, target):
        assert target == "plate.A1"
        return SimpleNamespace(x=10.0, y=20.0, z=2.0)


def test_interpolate_points_includes_endpoint():
    points = interpolate_points(Point3D(0, 0, 0), Point3D(10, 0, 0), step_mm=3)
    assert points[-1] == Point3D(10, 0, 0)
    assert len(points) == 4


def test_move_to_deck_target_uses_instrument_safe_approach_height():
    protocol = SimpleNamespace(
        positions={},
        steps=[
            SimpleNamespace(index=0, command_name="move", args={"instrument": "probe", "position": "plate.A1"})
        ],
    )
    planner = MotionPlanner(
        deck=FakeDeck(),
        protocol=protocol,
        instruments={"probe": InstrumentModel("probe", depth=5.0, safe_approach_height=30.0)},
        working_volume={"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100, "z_min": 0, "z_max": 80},
        sample_step_mm=50,
    )

    plan = planner.plan()
    target_points = [point for point in plan["path"] if point["targetRef"] == "deck:plate.A1"]

    assert target_points[-1]["tool"] == {"x": 10.0, "y": 20.0, "z": 30.0}
    assert target_points[-1]["gantry"] == {"x": 10.0, "y": 20.0, "z": 35.0}
