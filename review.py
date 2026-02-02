"""
Module: review.py

Author:
    Om Prakash Sahu

Created on:
    2025-04-07

Email:
    omprakash.sahu@saffronic.com

Description:
    This module handles review processes for various actions in the Shotgrid pipeline,
    including Team Lead (TL) and Supervisor (Sup) approvals, notes, and retakes.
    It supports actions from all departments by validating user roles, task statuses,
    and updating version and task data accordingly. The module integrates with
    Shotgrid API for data retrieval and updates, and generates HTML reports for
    review outcomes.

Dependencies:
    - os: For file path operations and environment variables.
    - json: For loading configuration files.
    - datetime: For timestamp generation in log files.
    - traceback: For error handling and logging.
    - utils.sg_global_utils: Custom utilities for Shotgrid data interactions.
    - utils.htmlGlobalLib: Custom library for HTML report generation.
    - config/fields_config.json: JSON file containing field mappings for Shotgrid entities.

Classes:
    - Review: Main class for handling review operations.

Usage:
    Instantiate the Review class with required parameters to perform review actions.
    The class automatically processes selected versions and tasks based on the action
    specified in the configuration.
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import os
import json
import ast
from datetime import datetime
import traceback

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------
from utils import sg_global_utils
import utils.html_global_lib as HtmlLib

with open(
    os.path.join(os.path.dirname(__file__), "config\\fields_config.json"),
    "r",
    encoding="utf-8",
) as CNFG:
    FIELDS = json.load(CNFG)


# pylint: disable=broad-except
class Review:
    """
    Handles review operations for Shotgrid pipeline tasks, including approvals, notes, and retakes.

    This class manages the review process by validating user permissions, task statuses,
    and updating Shotgrid entities accordingly. 
    It supports different actions (approve, note, retake)
    and generates detailed HTML reports of the review outcomes.

    Attributes:
        sg_obj (object): Shotgun API object for database interactions.
        sa_obj (object): Custom object with task selection and project metadata.
        logger (logging.Logger): Logger for tracking errors and debug information.
        project_name (str): Name of the current project.
        project_id (int): ID of the current project.
        config_data (dict): Configuration data for the selected action.
        valid_roles (list): List of valid roles for the action.
        current_user (dict): Data of the current user performing the review.
        task_config_data (list): Configuration data for task status mappings.
        versions (dict): Dictionary of version data keyed by version ID.
        tasks (dict): Dictionary of task data keyed by task ID.

    Methods:
        get_version_task_data(): Retrieves and organizes version and task data.
        update_version(): Validates and updates versions and tasks.
    """

    def __init__(self, sg_obj, sa_obj, logger, config_data):
        """
        Initializes the Review class instance and performs the review process.

        Sets up instance variables, retrieves necessary data from Shotgrid,
        executes the configured review function, and generates an HTML report.

        :param sg_obj: Shotgun API object used for database interactions.
        :type sg_obj: object
        :param sa_obj: Custom object containing task selection details and project metadata.
        :type sa_obj: object
        :param logger: Logging object for tracking errors and debug information.
        :type logger: logging.Logger
        :param config_data: Configuration data dictionary loaded from JSON file.
        :type config_data: dict
        """
        try:
            # Initialize core instance variables for Shotgrid interaction and logging
            self.sg_obj = sg_obj
            self.sa_obj = sa_obj
            self.logger = logger
            self.project_name = sa_obj.project["name"]
            self.project_id = sa_obj.project["id"]

            # Load configuration data specific to the selected action (e.g., approve, note, retake)
            self.config_data = config_data[sa_obj.action]

            # Extract valid roles allowed for this action from configuration
            self.valid_roles = config_data[self.sa_obj.action]["validRole"]

            # Create filter to retrieve current user data from Shotgrid HumanUser entity
            user_filter = [["id", "is", int(self.sa_obj.user["id"])]]
            self.logger.info(f"Current User Filter: {user_filter}")
            self.current_user = sg_global_utils.get_entity_data(
                sg_obj, sa_obj, logger, "HumanUser", filters=user_filter
            )[-1]

            # Retrieve project-specific configuration data for status mappings from CustomEntity24
            config_filter = [["project", "name_is", self.project_name]]
            self.task_config_data = sg_global_utils.get_entity_data(
                self.sg_obj, self.sa_obj, self.logger, "CustomEntity24", config_filter
            )

            # Fetch and organize version and task data into dictionaries for efficient processing
            self.versions, self.tasks = self.get_version_task_data()

            # Dynamically call the configured review function (e.g., update_version) based on action
            report_list = getattr(self, self.config_data["function"])()

            # Generate HTML report with review results
            file_path = config_data["logFolderPath"]
            file_name = os.getenv("USERNAME") + "_" + datetime.now().strftime("%H%M%S")
            file_obj, file_path = HtmlLib.open_html_file_to_path(
                logger,
                os.path.dirname(file_path),
                file_name,
                "Review Log",
                "Review_Log",
            )
            header_list = ["Version", "Task", "Success", "Reason"]
            data_list = []
            for each in report_list:
                each_data = []
                for _, value in each.items():
                    each_data.append(value)
                data_list.append(each_data)
            HtmlLib.write_header_data(logger, file_obj, "Overall Report")
            HtmlLib.write_table_data(logger, file_obj, header_list, data_list)
            HtmlLib.close_html_file(logger, file_obj, file_path)

        except Exception:
            self.logger.error(traceback.format_exc())

    def get_version_task_data(self):
        """
        Retrieves and organizes version and task data from Shotgrid for efficient processing.

        This method queries Shotgrid to fetch the selected versions based on the entity type
        specified in sa_obj. It extracts the associated task IDs from these versions and
        performs a batch query to retrieve all corresponding task data in a single API call.
        The data is then organized into dictionaries keyed by IDs for quick lookup during
        the review process, reducing the need for repeated database queries.

        :return: A tuple containing two dictionaries:
                 - version_dict (dict): Dictionary with version IDs as keys and 
                 full version data as values.
                 - tasks_dict (dict): Dictionary with task IDs as keys and 
                 full task data as values.
        :rtype: tuple(dict, dict)
        :raises Exception: If data retrieval from Shotgrid fails, logs the error and 
        returns empty dictionaries.
        """
        version_dict = {}
        tasks_dict = {}
        try:
            # Retrieve selected version data from Shotgrid based on entity type
            versions = sg_global_utils.get_entity_data(
                self.sg_obj, self.sa_obj, self.logger, self.sa_obj.entity_type
            )
            self.logger.error(f"Selected Versions: {versions}")

            # Extract task IDs from the retrieved versions for efficient batch retrieval
            task_ids_list = [task["sg_task"]["id"] for task in versions]

            # Organize version data into a dictionary keyed by version ID for quick access
            version_dict = {ver["id"]: ver for ver in versions}

            # Retrieve all associated task data in a single query using the task IDs
            task_filter = [["id", "in", task_ids_list]]
            task_data = sg_global_utils.get_entity_data(
                self.sg_obj, self.sa_obj, self.logger, "Task", filters=task_filter
            )
            tasks_dict = {task["id"]: task for task in task_data}

        except Exception:
            self.logger.error(traceback.format_exc())
        return version_dict, tasks_dict

    def update_version(self):
        """
        Validates and updates the selected versions and their associated tasks 
        based on review actions.

        This method iterates through each selected version, performs comprehensive validation
        including user permissions, task statuses, and configuration checks. It updates the
        status of tasks and versions in Shotgrid according to the configured status mappings.
        For techfix tasks, it also updates related CustomEntity04 records. All updates are
        batched for efficiency, and a detailed report is generated for each version/task pair.

        :return: A list of dictionaries, each containing the review result for a version/task pair.
                 Each dictionary includes 'Version', 'Task', 'Success', and 'Reason' keys.
        :rtype: list[dict]
        :raises Exception: If batch updates to Shotgrid fail, returns a failure report.
        """
        self.logger.info("Review : updateForApprove Started")
        report_list = []
        try:
            batch_data = []

            # Iterate through each selected version to validate and update
            for version_id, version in self.versions.items():

                # Initialize report dictionary for this version/task pair
                report_dict = {"Version": "", "Task": "", "Success": "", "Reason": ""}

                # Extract relevant data from version and associated task for processing
                ver_task_id = version["sg_task"]["id"]
                ver_status = version[FIELDS["Version"]["status"]]
                task = self.tasks.get(ver_task_id, None)
                task_status = task[FIELDS["Task"]["status"]]
                task_name = task[FIELDS["Task"]["taskName"]]
                split_type = task[FIELDS["Task"]["splitType"]]
                is_techfix = False

                # Populate report dictionary with version and task names
                report_dict["Version"] = version[FIELDS["Version"]["versionName"]]
                report_dict["Task"] = task[FIELDS["Task"]["pipelineStep"]]["name"]
                report_dict["Success"] = "NO"
                report_dict["Reason"] = ""

                # Determine configuration task name, handling techfix and split tasks
                config_task_name = task_name
                if str(task_name).endswith("_TechFix"):
                    is_techfix = True
                    config_task_name = str(task_name).split("_", maxsplit=1)[0]

                if split_type == "SPLIT":
                    config_task_name = str(task_name).split("_", maxsplit=1)[0]

                # Find matching configuration data for status mapping based on
                # entity type, pipeline step, and task name
                task_config_data = [
                    i
                    for i in self.task_config_data
                    if i[FIELDS["CustomEntity24"]["entityType"]]
                    in [task[FIELDS["Task"]["link"]]["type"]]
                    and i[FIELDS["CustomEntity24"]["pathSheetName"]]
                    in [task[FIELDS["Task"]["pipelineStep"]]["name"]]
                    and i[FIELDS["CustomEntity24"]["taskName"]] in [config_task_name]
                ]

                # Skip if no valid configuration is found
                if not task_config_data:
                    report_dict["Reason"] = (
                        "Valid config is not available in SG, please reach out to SG team!"
                    )
                    report_list.append(report_dict)
                    continue

                # Parse status configuration from the matched config data
                # using ast.literal_eval (assuming it's a string representation of a dict)
                status_config = ast.literal_eval(
                    task_config_data[-1][FIELDS["CustomEntity24"]["statusConfig"]]
                )

                if not status_config:
                    report_dict["Reason"] = (
                        "Valid status not updated in SG Status Config, please reach out to SG team!"
                    )
                    report_list.append(report_dict)
                    continue

                # Get status mapping for the current action (e.g., approve, note, retake)
                status_config = status_config[self.sa_obj.action]
                self.logger.info(f"statusConfig: {status_config}")

                # Get current user's role for permission validation
                user_role = self.current_user[FIELDS["HumanUser"]["userPermission"]][
                    "name"
                ]

                # Validate user role assignments, dates, and other constraints
                # using utility function
                valid_role_assignments, valid_role_assignment_msg = (
                    sg_global_utils.validate_role_assignments(
                        self.sg_obj, self.sa_obj, self.logger, task, self.valid_roles
                    )
                )

                if not valid_role_assignments:
                    report_dict["Reason"] = valid_role_assignment_msg
                    report_list.append(report_dict)
                    continue

                # Check permissions and status validity for Lead review
                # (user must be team lead and have valid statuses)
                if (
                    user_role in ["Lead", "Team Lead", "Admin", "Manager"]
                    and self.current_user["id"]
                    == task[FIELDS["Task"]["teamLead"]]["id"]
                ):
                    if task_status not in self.config_data["validLeadStatus"]:
                        report_dict["Reason"] = (
                            "Task status is not valid for the Lead review"
                        )
                        report_list.append(report_dict)
                        continue

                    if ver_status not in self.config_data["validLeadVerStatus"]:
                        report_dict["Reason"] = (
                            "Version status is not valid for the Lead review"
                        )
                        report_list.append(report_dict)
                        continue

                # Check permissions and status validity for Supervisor review
                # (user must be supervisor and have valid statuses)
                elif (
                    user_role in ["Supervisor", "Admin", "Team Lead", "Lead", "Manager"]
                    and self.current_user["id"]
                    == task[FIELDS["Task"]["supervisor"]]["id"]
                ):
                    if task_status not in self.config_data["validSupStatus"]:
                        report_dict["Reason"] = (
                            "Task status is not valid for the Supervisor review"
                        )
                        report_list.append(report_dict)
                        continue

                    if ver_status not in self.config_data["validSupVerStatus"]:
                        report_dict["Reason"] = (
                            "Version status is not valid for the Supervisor review"
                        )
                        report_list.append(report_dict)
                        continue

                else:
                    # User does not have permission to review this task (not lead or supervisor)
                    report_dict["Reason"] = (
                        "User is not valid to review the task, "
                        "Please check the Team Lead or Supervisor field and update accordingly!!"
                    )
                    report_list.append(report_dict)
                    continue

                # Prepare data for status update using the mapped status from config
                data_to_update = {
                    FIELDS["Task"]["status"]: status_config.get(task_status)
                }
                self.logger.info(f"Data to Update: {data_to_update}")

                # Handle techfix tasks by updating related CustomEntity04 records
                # (techfix data entries)
                if is_techfix:
                    tech_data_filter = [
                        [
                            FIELDS["CustomEntity04"]["task"],
                            "is",
                            {"type": "Task", "id": task["id"]},
                        ],
                        [
                            FIELDS["CustomEntity04"]["project"],
                            "is",
                            {"type": "Project", "id": self.project_id},
                        ],
                    ]
                    tech_data_entry = sg_global_utils.get_entity_data(
                        self.sg_obj,
                        self.sa_obj,
                        self.logger,
                        "CustomEntity04",
                        tech_data_filter,
                    )

                    if not tech_data_entry:
                        report_dict["Reason"] = (
                            "Selected Task TechFixData Record is not available in SG"
                        )
                        report_list.append(report_dict)
                        continue

                    tech_data_entry = tech_data_entry[-1]
                    batch_data.append(
                        {
                            "request_type": "update",
                            "entity_type": "CustomEntity04",
                            "entity_id": tech_data_entry["id"],
                            "data": data_to_update,
                        }
                    )

                # Add updates for Task and Version entities to batch for efficient processing
                batch_data.append(
                    {
                        "request_type": "update",
                        "entity_type": "Task",
                        "entity_id": task["id"],
                        "data": data_to_update,
                    }
                )
                batch_data.append(
                    {
                        "request_type": "update",
                        "entity_type": "Version",
                        "entity_id": version_id,
                        "data": data_to_update,
                    }
                )
                report_dict["Success"] = "YES"
                report_list.append(report_dict)

            # Execute all batched updates if any were prepared (single API call for all updates)
            if batch_data:
                self.sg_obj.batch(batch_data)

        except Exception:
            report_list = [
                {
                    "Version": "",
                    "Task": "",
                    "Success": "NO",
                    "Reason": traceback.format_exc(),
                }
            ]
            self.logger.error(
                "Review : updateForApprove failed - %s", traceback.format_exc()
            )
        return report_list
