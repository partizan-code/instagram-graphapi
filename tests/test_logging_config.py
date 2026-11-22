from logging_config import configure_logging, logger


def test_repeated_setup_does_not_duplicate_logs(capsys):
    configure_logging()
    configure_logging()
    logger.info("One record only")
    output = capsys.readouterr()
    assert output.err.count("One record only") == 1
    assert "INFO" in output.err
    assert output.out == ""


def test_debug_is_hidden_but_info_and_error_are_visible(capsys):
    logger.debug("debug-record")
    logger.info("info-record")
    logger.error("error-record")
    output = capsys.readouterr().err
    assert "debug-record" not in output
    assert "info-record" in output
    assert "error-record" in output
