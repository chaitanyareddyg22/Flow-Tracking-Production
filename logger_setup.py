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


def setup_logger(logger="SaffSgLogger", log_file=None):
    """
    This Function creates/retrun the existing logger with File Handler or 
    Stream handler based on the arguments
    
    :param logger: Logger Name, defaults to 'SaffSgLogger'
    :type logger: str, optional
    :param log_file: Logfile path, defaults to None
    :type log_file: str, optional
    :raises Exception: raises the IO Exception ifuser dont have write access to log directory
    :return: Logger Object
    :rtype: logging
    """
    try:
        logger = logging.getLogger(logger)

        # if already Handlers available return it
        if logger.hasHandlers():
            for each_handler in logger.handlers:
                if (
                    log_file
                    and isinstance(each_handler, logging.FileHandler)
                    and each_handler.baseFilename.endswith(log_file)
                ):
                    return logger
            return logger

        logger.setLevel(logging.INFO)

        # return Console handler, if LogFile is None
        if not log_file:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
            logger.addHandler(console_handler)
            return logger

        # check and create log directory, if not exist
        if not os.path.exists(os.path.dirname(log_file)):
            os.makedirs(os.path.dirname(log_file))

        if os.getenv("USERNAME") in DEVS:
            log_file = os.path.join(r"D:\SG_AMI_LOG", os.getenv("USERNAME") + ".log")

        # add File Handler and return logeger
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
