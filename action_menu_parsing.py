# ---------------------------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------------------------
"""
The values sent by the Action Menu Item are in the form of a GET request that is similar to the
format: myCoolProtocol://doSomethingCool?user_id=24&user_login=shotgun&title=All%20Versions&...

In a more human-readable state that would translate to something like this:
{
    'project_name': 'Demo Project',
    'user_id': '24',
    'title': 'All Versions',
    'user_login': 'shotgun',
    'sort_column': 'created_at',
    'entity_type': 'Version',
    'cols': 'created_at',
    'ids': '5,2',
    'selected_ids': '2,5',
    'sort_direction': 'desc',
    'project_id': '4',
    'session_uuid': 'd8592bd6-fc41-11e1-b2c5-000c297a5f50',
    'column_display_names': [
        'Version Name',
        'Thumbnail',
        'Link',
        'Artist',
        'Description',
        'Status',
        'Path to frames',
        'QT',
        'Date Created'
    ]
}

This simple class parses the URL into easily accessible variables from the parameters,
action, and protocol sections of the URL. For example:

    Example URL:
    myCoolProtocol://doSomethingCool?user_id=123&user_login=miled&title=All%20Versions&...

    Parsed Results:
    protocol: myCoolProtocol
    action: doSomethingCool
    params: {
        'user_id': '123',
        'user_login': 'miled',
        'title': 'All Versions',
        ...
    }

The parameters variable will be returned as a dictionary of string key/value pairs.
Here's how to instantiate and use the class:

    sa = ShotgunAction(sys.argv[1])  # Pass the URL as an argument
    sa.params['user_login']  # Returns 'miled'
    sa.params['user_id']  # Returns '123'
    sa.protocol  # Returns 'myCoolProtocol'
"""

# ---------------------------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------------------------
import traceback
import six

# ---------------------------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------------------------


# ---------------------------------------------------------------------------------------------
# Generic ShotgunActionException Class
# ---------------------------------------------------------------------------------------------
class ShotgunActionException(Exception):
    """
    Custom exception class for handling errors in the ShotgunAction class.
    """

    def __init__(self, message):
        super().__init__(f"ShotGrid Exception: '{message}'")


# ---------------------------------------------------------------------------------------------
# ShotgunAction Class to manage ActionMenuItem call
# ---------------------------------------------------------------------------------------------
class ShotgunAction:
    """
    A class to parse and manage the URL and parameters from an Action Menu Item call.

    Attributes:
        protocol (str): The protocol used in the URL.
        action (str): The action specified in the URL.
        params (dict): A dictionary of parameters extracted from the URL.
        entity_type (str): The type of entity.
        project (dict or None): Project information.
        columns (list): List of columns.
        column_display_names (list): Display names for columns.
        ids (list): List of IDs.
        ids_filter (list): Filter for IDs.
        selected_ids (list): List of selected IDs.
        selected_ids_filter (list): Filter for selected IDs.
        sort (dict or None): Sorting information.
        user (dict): User information.
        session_uuid (str): Session UUID.
    """

    def __init__(self, url, logger, sg_obj=None):
        """
        Initializes the ShotgunAction object and parses the provided URL.

        :param url: The URL to parse.
        :type url: str
        :param logger: Logger Object
        :type logger: Logger
        :param sg_obj: Shotgun Object, defaults to None
        :type sg_obj: optional
        """

        self.logger = logger
        self.url = url
        self.protocol, self.action, self.params = self._parse_url()

        if "event_log_entry_id" in self.params:
            self._light_payload(sg_obj)

        self.entity_type = self.params["entity_type"]

        # Project information
        if "project_id" in self.params:
            self.project = {
                "id": int(self.params["project_id"]),
                "name": self.params["project_name"],
            }
        else:
            self.project = None

        self.columns = self.params["cols"]
        self.column_display_names = self.params["column_display_names"]

        # IDs
        self.ids = []
        if len(self.params["ids"]) > 0:
            ids = self.params["ids"].split(",")
            self.ids = [int(id) for id in ids]
        self.ids_filter = self._convert_ids_to_filter(self.ids)

        self.selected_ids = []
        if len(self.params["selected_ids"]) > 0:
            sids = self.params["selected_ids"].split(",")
            self.selected_ids = [int(id) for id in sids]
        self.selected_ids_filter = self._convert_ids_to_filter(self.selected_ids)

        # Sorting
        if "sort_column" in self.params:
            self.sort = {
                "column": self.params["sort_column"],
                "direction": self.params["sort_direction"],
            }
        else:
            self.sort = None

        # self.title = self.params["title"]

        self.user = {
            "id": self.params["user_id"],
            "login": self.params["user_login"],
        }

        self.session_uuid = self.params["session_uuid"]

    def _light_payload(self, sg_obj):
        """
        This function handles the event log entry ID for the light payload.
        """
        try:
            event_log_id = int(self.params["event_log_entry_id"])
            sg_cols = ["entity", "meta"]
            event_data = sg_obj.find_one(
                "EventLogEntry", [["id", "is", int(event_log_id)]], sg_cols
            )
            if event_data:
                self.params = event_data["meta"]["ami_payload"]
        except Exception as e:
            print(traceback.format_exc())
            raise ShotgunActionException("SgotGrid Query Error") from e

    def _parse_url(self):
        """
        Parses the URL into protocol, action, and parameters.

        Returns:
            tuple: A tuple containing protocol, action, and parameters.
        """
        self.logger.info(f"Parsing full URL received: {self.url}")

        protocol, path = self.url.split(":", 1)
        self.logger.info(f"protocol: {protocol}")

        action, params = path.split("?", 1)
        action = action.strip("/")
        self.logger.info(f"action: {action}")

        params = params.split("&")
        p = {"column_display_names": [], "cols": []}
        for arg in params:
            key, value = map(six.moves.urllib.parse.unquote, arg.split("=", 1))
            if key in ["column_display_names", "cols"]:
                p[key].append(value)
            else:
                p[key] = value
        self.logger.info(f"params: {p}")
        return protocol, action, p

    def _convert_ids_to_filter(self, ids):
        """
        Converts a list of IDs into a filter format.

        Args:
            ids (list): A list of entity IDs.

        Returns:
            list: A filter-ready list of IDs.
        """
        filters = [["id", "is", id] for id in ids]
        self.logger.debug(f"parsed IDs into: {filters}")
        return filters


# ---------------------------------------------------------------------------------------------
# Main Block
# ---------------------------------------------------------------------------------------------
# if __name__ == "__main__":
#     try:
#         logger = logger_setup.setup_logger()
#         sa = ShotgunAction(sys.argv[1], logger)
#         print(f"ShotgunAction: Firing... {sys.argv[1]}")
#     except IndexError as e:
#         raise ShotgunActionException("Missing GET arguments") from e
#     print("ShotgunAction process finished.")
