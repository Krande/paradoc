import logging


def create_logger():
    logger = logging.getLogger("paradoc")
    return logger


logger = create_logger()
