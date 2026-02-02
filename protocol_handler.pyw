"""
Name:
    protocol_handler.pyw
Author:
    CHAITANYA REDDY G
Created on:
    2025-03-27
Email:
    chaitanya.reddygudeti@saffronic.com
Description:
    ShotGrid ProtocallHandler for Action Menu Items
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import sys
import os
import json
import datetime
import traceback
import importlib

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------
import logger_setup
import action_menu_parsing as AMP
import sg_connection

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config\\action_menu_config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as CNFG:
    CONFIG_DATA = json.load(CNFG)

os.environ["QT_API"] = "pyqt6"

DATE_FOLDER = datetime.datetime.now().strftime("%d%b%Y")
TIME_STAMP = datetime.datetime.now().strftime("%H%M%S")
LOG_FOLDER_PATH = CONFIG_DATA["logFolderPath"]
LOG_FILE_NAME = f'{os.getenv("USERNAME")}_{TIME_STAMP}.log'
LOGGER = logger_setup.setup_logger(
    log_file=os.path.join(LOG_FOLDER_PATH, DATE_FOLDER, LOG_FILE_NAME)
)


if __name__ == "__main__":
    try:
        url: str = sys.argv[1]

        print("Connecting to SG please wait...")
        # get the protocol used
        protocol, path = url.split(":", 1)
        LOGGER.info("protocol: %s", protocol)

        # extract the action
        action, params = path.split("?", 1)
        action = action.strip("/")
        LOGGER.info("action: %s", action)

        # Get shotgun connection object
        sg_obj = sg_connection.get_sg_connection(action, CONFIG_DATA)
        LOGGER.info("sgObj: %s", sg_obj)

        # Get shotgun action object
        sa_obj = AMP.ShotgunAction(url, LOGGER, sg_obj)
        LOGGER.info("Config Data Module: %s", CONFIG_DATA[action]["module"])
        LOGGER.info("saObj: %s", sa_obj)

        # import required module and class based on action
        module = importlib.import_module(CONFIG_DATA[action]["module"])
        LOGGER.info("module: %s", module)

        getattr(module, CONFIG_DATA[action]["class"])(
            sg_obj, sa_obj, LOGGER, CONFIG_DATA
        )

    except Exception as e:
        LOGGER.error("Error in main function - %s", traceback.format_exc())
        input("check above error")
        raise AMP.ShotgunActionException("Missing GET arguments")
    LOGGER.info("ShotgunAction process finished.")
