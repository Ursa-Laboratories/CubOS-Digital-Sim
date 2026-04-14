from digital_twin.exporter import MotionPose, _motion_segment


def test_motion_segment_uses_xy_phase_for_flat_move():
    segment = _motion_segment(
        start_pose=MotionPose(0.0, 0.0, 23.0),
        end_pose=MotionPose(12.0, 8.0, 23.0),
    )

    assert segment.phase == "traverse_xy"
    assert segment.start_pose == MotionPose(0.0, 0.0, 23.0)
    assert segment.end_pose == MotionPose(12.0, 8.0, 23.0)


def test_motion_segment_uses_lift_phase_for_z_increase():
    segment = _motion_segment(
        start_pose=MotionPose(12.0, 8.0, 20.0),
        end_pose=MotionPose(12.0, 8.0, 62.0),
    )

    assert segment.phase == "lift_z"
    assert segment.end_pose == MotionPose(12.0, 8.0, 62.0)


def test_motion_segment_uses_descend_phase_for_z_decrease():
    segment = _motion_segment(
        start_pose=MotionPose(10.0, 10.0, 30.0),
        end_pose=MotionPose(10.0, 10.0, 20.0),
    )

    assert segment.phase == "descend_z"
    assert segment.end_pose == MotionPose(10.0, 10.0, 20.0)


def test_motion_segment_uses_xyz_phase_for_diagonal_move():
    segment = _motion_segment(
        start_pose=MotionPose(0.0, 0.0, 80.0),
        end_pose=MotionPose(12.0, 8.0, 23.0),
    )

    assert segment.phase == "move_xyz"
    assert segment.distance_mm > 0
    assert segment.real_duration_s > 0
