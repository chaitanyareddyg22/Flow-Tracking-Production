"""
Name:
    logger_setup.py
Author:
    CHAITANYA REDDY G
Created on:
    2025-03-27
Email:
    chaitanya.reddygudeti@saffronic.com
Description:
    This Module used to setup the Logger
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import os
import logging
from logging.handlers import TimedRotatingFileHandler

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------
from action_menu_parsing import ShotgunActionException

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------
DEVS = ["CG001105031", "OS001105039", "KS001105033", "NN001105028"]


def setup_logger(
    logger="SaffSgLogger",
    log_file=None,
    use_rotating=False,
    when="D",
    interval=1,
    backup_count=7,
):
    """
    This Function creates/retrun the existing logger with File Handler,
    Stream handler or Timed Rotating File Handler based on the arguments

    :param logger: Logger Name, defaults to 'SaffSgLogger'
    :type logger: str, optional
    :param log_file: Logfile path, defaults to None
    :type log_file: str, optional
    :param use_rotating: Use TimedRotatingFileHandler when True, defaults to False
    :type use_rotating: bool, optional
    :param when: Time interval type ('S', 'M', 'H', 'D', 'midnight', 'W0'-'W6'), defaults to 'D'
    :type when: str, optional
    :param interval: Number of time units, defaults to 1
    :type interval: int, optional
    :param backup_count: Number of backup files to keep, defaults to 7
    :type backup_count: int, optional
    :raises Exception: raises the IO Exception ifuser dont have write access to log directory
    :return: Logger Object
    :rtype: logging
    """
    try:
        logger = logging.getLogger(logger)

        # If handlers already exist, check if requested file handler is present
        if logger.hasHandlers():
            if log_file:
                # Check if a matching FileHandler already exists
                for each_handler in logger.handlers:
                    if isinstance(
                        each_handler, logging.FileHandler
                    ) and each_handler.baseFilename.endswith(log_file):
                        return logger
                # If not found, fall through to create a new file handler
            else:
                # No log_file requested → just reuse existing handlers
                return logger

        logger.setLevel(logging.INFO)

        # return Console handler, if LogFile is None
        if not log_file:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
            logger.addHandler(console_handler)
            return logger

        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Developer-specific override
        user = os.getenv("USERNAME") or os.getenv("USER")
        if user in DEVS:
            use_rotating = False
            log_file = os.path.join(r"D:\SG_AMI_LOG", f"{user}.log")
            if logger.name in ['ServerLogger']:
                log_file = os.path.join(r"D:\SG_AMI_LOG", "notification.log")

        # Time-based rotating file handler
        # Example: rotate every midnight, keep 7 backups
        if use_rotating:
            file_handler = TimedRotatingFileHandler(
                log_file,
                when=when,  # rotate every day
                interval=interval,  # every 1 day
                backupCount=backup_count,  # keep last 7 log files
                encoding="utf-8",
            )
        # Normal File Handler
        else:
            file_handler = logging.FileHandler(log_file, "w")

        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - [Line %(lineno)d] - %(message)s"
            )
        )
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.info("ShotgunAction logging started.")
        return logger
    except IOError as e:
        print(f"Error occurred - {e}")
        input("Please check above Error")
        raise ShotgunActionException("Unable to open logfile for writing") from e
