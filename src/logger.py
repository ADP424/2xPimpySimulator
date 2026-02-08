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
        return f"{record.asctime} {record.levelname} — {record.name} — {record.message}"


def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(ColorFormatter())
        logger.addHandler(handler)
    return logger
