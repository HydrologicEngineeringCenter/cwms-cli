import logging

from cwmscli.utils.logging import _ExternalLogFilter


def _record(name: str, level: int) -> logging.LogRecord:
    return logging.LogRecord(name, level, "test.py", 1, "message", (), None)


def test_httpx_info_is_hidden_when_debug_is_disabled():
    root_logger = logging.getLogger()
    original_level = root_logger.level
    try:
        root_logger.setLevel(logging.INFO)
        assert not _ExternalLogFilter().filter(_record("httpx", logging.INFO))
    finally:
        root_logger.setLevel(original_level)


def test_httpx_info_is_relabelled_as_debug_when_debug_is_enabled():
    root_logger = logging.getLogger()
    original_level = root_logger.level
    try:
        root_logger.setLevel(logging.DEBUG)
        record = _record("httpx._client", logging.INFO)

        assert _ExternalLogFilter().filter(record)
        assert record.levelno == logging.DEBUG
        assert record.levelname == "DEBUG"
    finally:
        root_logger.setLevel(original_level)


def test_filter_leaves_other_logger_messages_unchanged():
    record = _record("cwmscli.usgs", logging.INFO)

    assert _ExternalLogFilter().filter(record)
    assert record.levelno == logging.INFO


def test_geopandas_fallback_warning_is_suppressed():
    record = _record(
        "dataretrieval.ogc.shaping",
        logging.WARNING,
    )
    record.msg = (
        "Geopandas not installed. Geometries will be flattened into pandas DataFrames."
    )

    assert not _ExternalLogFilter().filter(record)


def test_other_dataretrieval_warnings_are_preserved():
    record = _record("dataretrieval.ogc.shaping", logging.WARNING)

    assert _ExternalLogFilter().filter(record)
