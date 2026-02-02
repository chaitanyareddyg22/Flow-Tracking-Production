"""
Publish Module for ShotGrid Task Operations.

This module provides functionality to publish ShotGrid tasks to the main server.
It includes validation, file copying, status updates, and logging for task publishing
processes in a production pipeline.

Author:
    CHAITANYA REDDY G
Created on:
    2025-04-09
Email:
    chaitanya.reddygudeti@saffronic.com

Dependencies:
    - qtpy: For Qt widgets.
    - sg_file_operations: Custom module for file operations.
    - utils.sg_global_utils: Global utilities for ShotGrid.
    - utils.html_global_lib: HTML generation utilities.

Usage:
    Instantiate the Publish class with required parameters and call the publish method.
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import json
import os
import sys
import re
import ast
import traceback
from datetime import datetime

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------
from qtpy import QtWidgets

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------
import sg_file_operations
from utils import sg_global_utils
from utils import html_global_lib as HtmlLib

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------
with open(
    os.path.join(os.path.dirname(__file__), "config\\fields_config.json"),
    "r",
    encoding="utf-8",
) as CNFG:
    FIELDS = json.load(CNFG)

# Initiate an App
APP = QtWidgets.QApplication(sys.argv)


# pylint: disable=broad-except
class Publish:
    """
    Handles the publishing of ShotGrid tasks to the main server.

    This class performs validations, file copying, status updates, and generates
    HTML reports for task publishing operations in a production pipeline.

    Raises:
        Exception: If initialization fails due to missing data or errors.
    """

    def __init__(self, sg_obj, sa_obj, logger, config_data):
        """
        Initializes the Publish class with necessary objects and data.

        Sets up instance variables, fetches task data, retrieves configurations,
        and executes the publish process, generating an HTML report.

        Args:
            sg_obj (object): Shotgun API object for database interactions.
            sa_obj (object): Custom object with task selection and project metadata.
            logger (logging.Logger): Logger for tracking errors and debug info.
            config_data (dict): Configuration data dict loaded from JSON file.

        Raises:
            Exception: If initialization or publishing fails.
        """
        try:
            self.sg_obj = sg_obj
            self.sa_obj = sa_obj
            self.logger = logger
            self.valid_roles = config_data[sa_obj.action]["validRole"]
            self.project_name = sa_obj.project["name"]
            self.project_id = sa_obj.project["id"]
            self.task_fields = FIELDS["Task"]
            self.config_data = config_data[sa_obj.action]

            # Fetch task data from ShotGrid
            self.selected_tasks_data = sg_global_utils.get_entity_data(
                sg_obj, sa_obj, logger, sa_obj.entity_type
            )
            if not self.selected_tasks_data:
                QtWidgets.QMessageBox.critical(
                    None, "Error", "Selected tasks data is not found in SG"
                )
                return

            # Retrieve published file types
            self.publish_types = sg_obj.find(
                "PublishedFileType", [["code", "is_not", None]], ["code"]
            )
            logger.info(f"publish_types: {self.publish_types}")

            # Retrieve submission configuration and status mapping for the project
            config_filter = [["project", "name_is", self.project_name]]
            self.task_config_data = sg_global_utils.get_entity_data(
                self.sg_obj, self.sa_obj, self.logger, "CustomEntity24", config_filter
            )

            # Execute the publish function dynamically
            report_list = getattr(self, self.config_data["function"])()

            # Generate HTML report after publishing
            file_path = config_data["logFolderPath"]
            file_name = (
                os.getenv("USERNAME") + "_" + datetime.now().strftime("%d%b%Y %H%M%S")
            )
            file_obj, file_path = HtmlLib.open_html_file_to_path(
                logger,
                os.path.dirname(file_path),
                file_name,
                "Publish Log",
                "Publish_Log",
            )
            header_list = ["Shot/Asset", "Task", "Success", "Reason"]
            data_list = []
            for each in report_list:
                each_data = []
                for _, value in each.items():
                    each_data.append(value)
                data_list.append(each_data)
            HtmlLib.write_header_data(logger, file_obj, "Overall Report")
            HtmlLib.write_table_data(logger, file_obj, header_list, data_list)
            HtmlLib.close_html_file(logger, file_obj, file_path)

        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(None, "Error", str(e))

    def publish(self):
        """
        Publishes all selected tasks after performing required validations.

        This method iterates through selected tasks, validates configurations,
        copies files to publish locations, updates task statuses in ShotGrid,
        and handles techfix and asset status updates.

        Returns:
            list: List of dictionaries containing the status of each selected task.
                 Each dict has keys: 'Shot/Asset', 'Task', 'Success', 'Reason'.

        Raises:
            Exception: If an error occurs during publishing.
        """
        report_list = []
        batch_data = []
        publish_batch_data = []
        try:
            for task in self.selected_tasks_data:
                # Initialize report_dict values each time
                report_dict = {
                    "Shot/Asset": task[self.task_fields["link"]]["name"],
                    "Task": task[self.task_fields["pipelineStep"]]["name"],
                    "Success": "NO",
                    "Reason": "",
                }

                # Retrieve entity details
                task_entity = task[self.task_fields["link"]]
                is_techfix = False
                entity_filters = [
                    ["code", "is", task_entity["name"]],
                    ["project", "name_is", self.project_name],
                ]
                entity_data = sg_global_utils.get_entity_data(
                    self.sg_obj,
                    self.sa_obj,
                    self.logger,
                    task_entity["type"],
                    entity_filters,
                )
                if not entity_data:
                    report_dict["Reason"] = (
                        "Selected Shot/Asset data is not found in SG"
                    )
                    report_list.append(report_dict)
                    continue
                entity_data = entity_data[-1]

                # Extract pipeline step and status information
                pipeline_step = task[self.task_fields["pipelineStep"]]["name"]
                current_status = task[self.task_fields["status"]]
                task_name = task[self.task_fields["taskName"]]
                split_type = task[self.task_fields["splitType"]]

                config_task_name = task_name
                # Check if selected task is Techfix task
                if str(task_name).endswith("_TechFix"):
                    is_techfix = True
                    config_task_name = str(task_name).split("_", maxsplit=1)[0]

                # Check if selected task is Splitted Task
                if split_type == "SPLIT":
                    config_task_name = str(task_name).split("_", maxsplit=1)[0]

                # Retrieve File configuration and status mapping
                task_config = [
                    i
                    for i in self.task_config_data
                    if i[FIELDS["CustomEntity24"]["entityType"]]
                    in [task[self.task_fields["link"]]["type"]]
                    and i[FIELDS["CustomEntity24"]["pathSheetName"]]
                    in [task[self.task_fields["pipelineStep"]]["name"]]
                    and i[FIELDS["CustomEntity24"]["taskName"]] in [config_task_name]
                ]

                # Check if Config is empty
                if not task_config:
                    report_dict["Reason"] = (
                        "Valid config is not available in SG, please reach out to SG team!"
                    )
                    report_list.append(report_dict)
                    continue

                task_config = task_config[-1]

                status_config = (
                    ast.literal_eval(task_config[FIELDS["CustomEntity24"]["statusConfig"]])
                    if task_config[FIELDS["CustomEntity24"]["statusConfig"]]
                    else None
                )
                task_file_configs = (
                    ast.literal_eval(task_config[FIELDS["CustomEntity24"]["fileConfig"]])
                    if task_config[FIELDS["CustomEntity24"]["fileConfig"]]
                    else None
                )
                qc_process = task_config[FIELDS["CustomEntity24"]["qcProcess"]]

                if pipeline_step not in self.config_data["clientQcSteps"]:
                    if not status_config or not task_file_configs:
                        report_dict["Reason"] = (
                            "Shotgrid Config is Empty for this Task, Please check with SG Team"
                        )
                        report_list.append(report_dict)
                        continue

                status_config = status_config[self.sa_obj.action]

                if is_techfix or not qc_process:
                    status_config.update({"tlapr": "pub", "movapr": "pub"})
                if (
                    pipeline_step not in self.config_data["clientQcSteps"]
                    and current_status not in status_config
                ):
                    report_dict["Reason"] = (
                        "Selected Task current status is not valid for this Action in SG"
                    )
                    report_list.append(report_dict)
                    continue

                # Validate user role, assignments and start/due dates
                valid_role_assignments, valid_role_assignment_msg = (
                    sg_global_utils.validate_role_assignments(
                        self.sg_obj, self.sa_obj, self.logger, task, self.valid_roles
                    )
                )
                if not valid_role_assignments:
                    report_dict["Reason"] = valid_role_assignment_msg
                    report_list.append(report_dict)
                    continue

                # isValidDates, datesMsg = sg_global_utils.validateStartDueDates(
                #     self.sgObj,
                #     self.logger,
                #     task[self.taskFields["startDate"]],
                #     task[self.taskFields["dueDate"]]
                # )
                # if not isValidDates:
                #     reportDict['Reason'] = datesMsg
                #     reportList.append(reportDict)
                #     continue

                # Determine next status and required file configurations
                next_status = status_config[current_status]
                file_configs = (
                    task_file_configs.get(next_status, None)
                    if task_file_configs
                    else {}
                )

                # Handle special cases for file configurations
                if task_file_configs and not file_configs:
                    if pipeline_step in ["Lighting"]:
                        file_configs = task_file_configs.get("movcpt")
                    else:
                        file_configs = task_file_configs.get("cmpt", {})

                overall_status = True
                overall_msg = ""
                for each in file_configs:
                    if not file_configs[each]["workarea"]:
                        continue
                    # Note: This regex works only with single file patterns like "Maya Files(*.ma)"
                    # Regex pattern to extract extensions
                    pattern = r"\*\.(\w+)"
                    # Extract extensions
                    extension = re.search(pattern, file_configs[each]["filter"])
                    extension = extension.group(1) if extension else ""
                    source = sg_global_utils.build_template_path(
                        self.sg_obj,
                        self.sa_obj,
                        self.logger,
                        task_config[
                            FIELDS["CustomEntity24"][file_configs[each]["workarea"]]
                        ],
                        extension,
                        task,
                        entity_data,
                        True,
                    )
                    if (
                        not os.path.exists(source)
                        and not file_configs[each]["mandatory"]
                    ):
                        continue
                    print(f"{each} is Copying, Please wait.......")
                    for each_tag in self.config_data["publishTags"]:
                        if not file_configs[each][each_tag]:
                            continue
                        destination = sg_global_utils.build_template_path(
                            self.sg_obj,
                            self.sa_obj,
                            self.logger,
                            task_config[
                                FIELDS["CustomEntity24"][file_configs[each][each_tag]]
                            ],
                            extension,
                            task,
                            entity_data,
                            True,
                        )
                        # Special condition for props assets in Texture pipeline step
                        if (
                            entity_data["type"] in ["Asset"]
                            and entity_data[FIELDS["Asset"]["assetType"]] in ["props"]
                            and each_tag in ["server"]
                            and pipeline_step in ["Texture"]
                        ):
                            destination = destination.replace(r"\workarea", "").replace(
                                "/workarea", ""
                            )
                            destination = destination.replace(r"\texture", "").replace(
                                "/texture", ""
                            )
                        # Handle file and folder copying
                        ignore = (
                            self.config_data["ignores"]
                            if each == "Unreal Folder"
                            else []
                        )
                        copy_status, msg = sg_file_operations.copy(
                            source,
                            destination,
                            self.logger,
                            ignores=ignore,
                            overwrite=True,
                            buffer=25 * 1024 * 1024,
                        )
                        overall_status = overall_status and copy_status
                        if copy_status:
                            publish_data = self.get_published_file_data(
                                task, each, destination
                            )
                            if publish_data:
                                publish_batch_data.append(
                                    {
                                        "request_type": "create",
                                        "entity_type": "PublishedFile",
                                        "data": publish_data,
                                    }
                                )
                            else:
                                overall_status = overall_status and False
                                overall_msg = (
                                    overall_msg
                                    + "Error During creating PublishFile Record in ShotGrid; "
                                )
                        else:
                            overall_msg = msg + overall_msg

                if overall_status:

                    update_data = {
                        self.task_fields["status"]: next_status,
                    }

                    # Check and update Techfix data Entry
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
                                "data": update_data,
                            }
                        )
                        tech_from_task = tech_data_entry[
                            FIELDS["CustomEntity04"]["from"]
                        ]

                        if not tech_from_task:
                            report_dict["Reason"] = (
                                "Selected Task TechFixData Record is not having"
                                "Source Task Data to update as TechFix Done,"
                                "Please check with SG Team"
                            )
                            report_list.append(report_dict)
                            continue

                        tech_from_task_data = sg_global_utils.get_entity_data(
                            self.sg_obj,
                            self.sa_obj,
                            self.logger,
                            "Task",
                            [["id", "is", tech_from_task["id"]]],
                        )
                        tech_from_task_status = tech_from_task_data[-1][
                            self.task_fields["status"]
                        ]

                        if tech_from_task_status in ["tfhl"]:
                            # Check if any other techfixes are pending for the From Task
                            # which raised the current techfix
                            # If all are done, update the From Task as Techfix Done
                            from_task_wip_filter = [
                                [
                                    FIELDS["CustomEntity04"]["from"],
                                    "is",
                                    tech_from_task,
                                ],
                                [
                                    FIELDS["CustomEntity04"]["task"],
                                    "is_not",
                                    {"type": "Task", "id": task["id"]},
                                ],
                                [
                                    FIELDS["CustomEntity04"]["project"],
                                    "is",
                                    {"type": "Project", "id": self.project_id},
                                ],
                                [
                                    FIELDS["CustomEntity04"]["status"],
                                    "not_in",
                                    ["pub", "omt", "reject"],
                                ],
                            ]
                            from_task_wip_techfixes = sg_global_utils.get_entity_data(
                                self.sg_obj,
                                self.sa_obj,
                                self.logger,
                                "CustomEntity04",
                                from_task_wip_filter,
                            )
                            self.logger.info(
                                f"from_task_wip_techfixes: {from_task_wip_techfixes}"
                            )
                            if not from_task_wip_techfixes:
                                batch_data.append(
                                    {
                                        "request_type": "update",
                                        "entity_type": "Task",
                                        "entity_id": tech_from_task["id"],
                                        "data": {self.task_fields["status"]: "thdn"},
                                    }
                                )
                            else:
                                self.logger.info(
                                    "Few Techfixes are pending, So we are not updating status"
                                )

                    # Update Asset Status
                    if entity_data["type"] in ["Asset"]:
                        asset_data = {}
                        if pipeline_step in ["Rig"]:
                            asset_data = {self.task_fields["status"]: "rfa"}
                        elif pipeline_step in ["LooknFeel", "Texture"]:
                            asset_data = {self.task_fields["status"]: "rflgt"}
                        elif pipeline_step in ["RigClientQC"]:
                            lgt_qc_filters = [
                                [
                                    self.task_fields["project"],
                                    "name_is",
                                    self.project_name,
                                ],
                                [
                                    self.task_fields["pipelineStep"],
                                    "name_is",
                                    "LgtClientQC",
                                ],
                                [self.task_fields["link"], "is", task_entity],
                            ]
                            lgt_qc_task = sg_global_utils.get_entity_data(
                                self.sg_obj,
                                self.sa_obj,
                                self.logger,
                                "Task",
                                lgt_qc_filters,
                            )
                            if not lgt_qc_task:
                                report_dict["Reason"] = (
                                    "LgtClientQC Task is not available in SG"
                                )
                                report_list.append(report_dict)
                                continue
                            lgt_qc_task = lgt_qc_task[-1]
                            if next_status in ["pub"] and lgt_qc_task[
                                self.task_fields["status"]
                            ] in ["pub"]:
                                asset_data = {self.task_fields["status"]: "rfp"}
                        elif pipeline_step in ["LgtClientQC"]:
                            rig_qc_filters = [
                                [
                                    self.task_fields["project"],
                                    "name_is",
                                    self.project_name,
                                ],
                                [
                                    self.task_fields["pipelineStep"],
                                    "name_is",
                                    "RigClientQC",
                                ],
                                [self.task_fields["link"], "is", task_entity],
                            ]
                            rig_qc_task = sg_global_utils.get_entity_data(
                                self.sg_obj,
                                self.sa_obj,
                                self.logger,
                                "Task",
                                rig_qc_filters,
                            )
                            if not rig_qc_task:
                                report_dict["Reason"] = (
                                    "RigClientQC Task is not available in SG"
                                )
                                report_list.append(report_dict)
                                continue
                            rig_qc_task = rig_qc_task[-1]
                            if next_status in ["pub"] and rig_qc_task[
                                self.task_fields["status"]
                            ] in ["pub"]:
                                asset_data = {self.task_fields["status"]: "rfp"}

                        if asset_data:
                            batch_data.append(
                                {
                                    "request_type": "update",
                                    "entity_type": entity_data["type"],
                                    "entity_id": entity_data["id"],
                                    "data": asset_data,
                                }
                            )

                    batch_data.append(
                        {
                            "request_type": "update",
                            "entity_type": "Task",
                            "entity_id": task["id"],
                            "data": update_data,
                        }
                    )
                    batch_data.extend(publish_batch_data)
                    report_dict["Success"] = "YES"
                    report_dict["Reason"] = "Task is Successfully Published"
                    report_list.append(report_dict)
                else:
                    report_dict["Reason"] = overall_msg
                    report_list.append(report_dict)

            if batch_data:
                self.sg_obj.batch(batch_data)

        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(None, "Error", str(e))
            report_list = [
                {
                    "Shot/Asset": "",
                    "Task": "",
                    "Success": "NO",
                    "Reason": traceback.format_exc(),
                }
            ]
        return report_list

    def get_published_file_data(self, task_data, file_type, path):
        """
        Creates the data dictionary for updating ShotGrid PublishedFile entity.

        This method constructs the necessary data to create a new PublishedFile
        record in ShotGrid, including project, entity, task, and file details.

        Args:
            task_data (dict): Selected task data containing entity and pipeline info.
            file_type (str): Type of published file (e.g., 'Maya File', 'Mov File').
            path (str): Absolute path of the published file.

        Returns:
            dict: Data dictionary for creating PublishedFile in ShotGrid, or empty dict on error.

        Raises:
            Exception: If data construction fails, logs the error.
        """
        data = {}
        try:
            client_pass = (
                task_data[self.task_fields["clientVersion"]]
                if task_data[self.task_fields["clientVersion"]]
                else 0
            )

            entity_type = task_data[self.task_fields["link"]]["type"]
            entity_name = task_data[self.task_fields["link"]]["name"]
            entity_id = task_data[self.task_fields["link"]]["id"]
            publish_code = (
                entity_name
                + "_"
                + task_data[self.task_fields["pipelineStep"]]["name"]
                + "_v"
                + str(client_pass).zfill(3)
            )
            publish_file_type = [
                i for i in self.publish_types if i["code"] in [file_type]
            ]
            version_fields = FIELDS["Version"]
            version_filters = [
                [version_fields["link"], "is", {"type": entity_type, "id": entity_id}],
                [
                    version_fields["task"],
                    "is",
                    {"type": "Task", "id": int(task_data["id"])},
                ],
                [version_fields["status"], "in", ["qcap"]],
            ]
            order = [{"field_name": "created_at", "direction": "asc"}]
            latest_version = self.sg_obj.find(
                "Version", version_filters, ["code"], order=order
            )
            latest_version = latest_version[-1] if latest_version else None
            code = os.path.basename(path) if os.path.isfile(path) else publish_code

            data = {
                "project": {"type": "Project", "id": self.sa_obj.project["id"]},
                "name": publish_code,
                "code": code,
                "sg_status_list": "cmpt",
                "version_number": int(client_pass),
                "published_file_type": (
                    publish_file_type[-1] if publish_file_type else None
                ),
                "entity": {"type": entity_type, "id": entity_id},
                "task": {"type": "Task", "id": int(task_data["id"])},
                "version": latest_version,
                "sg_absolute_path": path,
            }
        except Exception:
            self.logger.error(traceback.format_exc())

        return data
