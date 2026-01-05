"""
Tests for voice_pipeline.context session_id resolution.
"""

from voice_pipeline.context import build_dispatch_context, parse_job_metadata, resolve_session_id


def test_parse_job_metadata_empty():
    assert parse_job_metadata(None) == {}
    assert parse_job_metadata("") == {}


def test_parse_job_metadata_non_json():
    assert parse_job_metadata("not-json") == {}


def test_parse_job_metadata_json_object():
    assert parse_job_metadata('{"flow":"compact"}') == {"flow": "compact"}


def test_resolve_session_id_prefers_job_metadata():
    sid = resolve_session_id(
        room_name="call-xyz",
        job_metadata='{"session_id":"sess_123","flow":"compact"}',
        participant_attributes={"session_id": "sess_attr"},
    )
    assert sid == "sess_123"


def test_resolve_session_id_falls_back_to_participant_attributes():
    sid = resolve_session_id(
        room_name="call-xyz",
        job_metadata='{"flow":"compact"}',
        participant_attributes={"session_id": "sess_attr"},
    )
    assert sid == "sess_attr"


def test_resolve_session_id_falls_back_to_room_name():
    sid = resolve_session_id(
        room_name="call-xyz",
        job_metadata='{"flow":"compact"}',
        participant_attributes={"other": "x"},
    )
    assert sid == "call-xyz"


def test_build_dispatch_context_includes_flow():
    ctx = build_dispatch_context(
        room_name="call-xyz",
        job_metadata='{"flow":"compact"}',
        participant_attributes=None,
    )
    assert ctx.session_id == "call-xyz"
    assert ctx.flow == "compact"


