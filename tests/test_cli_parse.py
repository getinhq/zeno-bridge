from zeno_bridge.cli import _parse_zeno_url


def test_parse_zeno_url_token():
    assert _parse_zeno_url("zeno://launch?token=abc123") == "abc123"


def test_parse_zeno_url_missing():
    assert _parse_zeno_url("zeno://launch") is None
