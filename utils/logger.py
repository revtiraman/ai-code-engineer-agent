import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger with a consistent format.
    Safe to call multiple times — handlers are not duplicated.
    """

    logger = logging.getLogger(name)

    if not logger.handlers:

        handler = logging.StreamHandler(sys.stdout)

        formatter = logging.Formatter(
            fmt="%(asctime)s  [%(name)-20s]  %(levelname)-8s  %(message)s",
            datefmt="%H:%M:%S"
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
