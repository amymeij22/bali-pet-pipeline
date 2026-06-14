import logging
from datetime import datetime
from biometeo_worker.logger import setup_logging, get_logger, _UtcFormatter

def test_logger_flow():
    # Test get_logger
    logger = get_logger("test_pet")
    assert isinstance(logger, logging.Logger)
    
    # Test setup_logging
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    root.handlers = []
    
    logger = setup_logging(logging.DEBUG)
    assert len(root.handlers) == 1
    
    # Test formatter execution
    formatter = root.handlers[0].formatter
    assert isinstance(formatter, _UtcFormatter)
    
    # Create a dummy log record
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="test message",
        args=(),
        exc_info=None
    )
    
    # Test formatTime with and without datefmt
    formatted_time_default = formatter.formatTime(record)
    assert len(formatted_time_default) == 19  # YYYY-MM-DD HH:MM:SS is 19 chars
    
    formatted_time_custom = formatter.formatTime(record, "%Y")
    assert len(formatted_time_custom) == 4  # e.g., '2026'
    
    # Test setup_logging when handlers already exist
    logger2 = setup_logging(logging.INFO)
    assert len(root.handlers) == 1  # Should reuse rather than adding another
    
    # Restore original handlers
    root.handlers = original_handlers
