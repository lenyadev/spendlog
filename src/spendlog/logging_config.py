import sys

from loguru import logger

from spendlog.settings import LogLevel


def setup_logging(log_level: LogLevel):
    logger.remove()
    logger.add(sys.stdout, serialize=True, level=log_level)
    return logger
