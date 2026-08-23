from services.event_consumer.processor import peek_event_id, parse_payload


def test_peek_event_id_reads_json() -> None:
    assert peek_event_id('{"event_id":"evt_1"}') == "evt_1"


def test_peek_event_id_returns_none_for_invalid_json() -> None:
    assert peek_event_id("not-json") is None


def test_parse_payload_wraps_raw_text() -> None:
    assert parse_payload("not-json") == {"raw": "not-json"}


def test_parse_payload_keeps_objects() -> None:
    assert parse_payload('{"event_id":"evt_1"}') == {"event_id": "evt_1"}
