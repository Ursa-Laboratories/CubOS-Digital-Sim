from digital_twin.geometry import AABB, Point3D, instrument_envelope
from digital_twin.motion import collision_warnings


def test_aabb_intersection_and_separation():
    deck_box = AABB(Point3D(0, 0, 0), Point3D(10, 10, 10), "box")
    touching = AABB(Point3D(9, 9, 9), Point3D(12, 12, 12), "touching")
    far = AABB(Point3D(14, 10, 10), Point3D(20, 20, 20), "far")

    assert deck_box.intersects(touching)
    assert not deck_box.intersects(far)
    assert far.separation_mm(deck_box) == 4
    assert deck_box.intersects(far, tolerance_mm=4)


def test_collision_warnings_skip_intended_deck_target():
    plate = AABB(Point3D(0, 0, 0), Point3D(20, 20, 10), "plate", "well_plate")
    rack = AABB(Point3D(30, 0, 0), Point3D(40, 20, 10), "rack", "tip_rack")
    path = [
        {
            "stepIndex": 0,
            "index": 1,
            "instrument": "asmi",
            "targetRef": "deck:plate.A1",
            "envelope": instrument_envelope(Point3D(10, 10, 0), depth_mm=30).to_json(),
        },
        {
            "stepIndex": 1,
            "index": 2,
            "instrument": "asmi",
            "targetRef": "literal",
            "envelope": instrument_envelope(Point3D(35, 10, 0), depth_mm=30).to_json(),
        },
    ]

    warnings = collision_warnings(path, [plate, rack])
    assert [warning["object"] for warning in warnings] == ["rack"]
