import logging


class ColorFormatter(logging.Formatter):
    GREY = "\033[38;5;248m"
    PURPLE = "\033[38;5;129m"
    BLUE = "\033[38;5;32m"
    RESET = "\033[0m"

    def format(self, record):
        record.asctime = f"{self.GREY}{self.formatTime(record)}{self.RESET}"
        record.levelname = f"{self.PURPLE}{record.levelname}{self.RESET}"
        record.name = f"{self.BLUE}{record.name}{self.RESET}"
        record.message = record.getMessage()
        s = f"{record.asctime} {record.levelname} — {record.name} — {record.message}"
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            s += "\n" + record.exc_text
        return s


def get_logger(name: str):
    """
    Get logger.

    Parameters
    ----------
    name: Any
        The `name` value.

    Returns
    -------
    Any
        The result of calling `get_logger`.
    """

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(ColorFormatter())
        logger.addHandler(handler)
    return logger
