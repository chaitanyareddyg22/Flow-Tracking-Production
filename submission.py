"""
This module handles all department submissions in ShotGrid.

It provides a Qt-based dialog class for submitting files, updating task statuses,
and managing configurations for various departments in the ShotGrid project management system.

Author: CHAITANYA REDDY G
Created on: 2025-04-01
Email: chaitanya.reddygudeti@saffronic.com
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import json
import os
import ast
import sys
import traceback
import glob
import re
import mimetypes
import fnmatch
from functools import partial
from collections import defaultdict

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------
from qtpy import QtWidgets, uic
from qtpy import QtCore

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------
from utils import sg_global_utils
from action_menu_parsing import ShotgunActionException
import sg_file_operations

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------
# Load UI Type
FORM_CLASS, BASE_CLASS = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ui\\submission.ui")
)

with open(
    os.path.join(os.path.dirname(__file__), "config\\fields_config.json"),
    "r",
    encoding="utf-8",
) as CNFG:
    FIELDS = json.load(CNFG)

# Initiate an App
APP = QtWidgets.QApplication(sys.argv)


# pylint: disable=broad-except
class Submission(FORM_CLASS, BASE_CLASS):
    """
    A Qt-based dialog class for handling task submissions in ShotGrid.

    This class provides a user interface for submitting files and updating task statuses
    for various departments in the ShotGrid project management system. It validates
    task data, manages file uploads, and ensures compliance with project configurations.
    """

    def __init__(self, sg_obj, sa_obj, logger, config_data):
        """
        Initializes the class instance, sets up UI elements, and validates task-related data.

        :param sg_obj: Shotgun API object used for database interactions.
        :type sg_obj: object
        :param sa_obj: Custom object containing task selection details and project metadata.
        :type sa_obj: object
        :param logger: Logging object for tracking errors and debug information.
        :type logger: logging.Logger
        :param config_data: Config Data dict loaded from json file
        :type config_data: dict
        """
        try:
            super().__init__()
            self.setupUi(self)

            # Initialize instance variables
            self.sg_obj = sg_obj
            self.sa_obj = sa_obj
            self.logger = logger
            self.dynamic_line_edit_dict = {}
            self.dynamic_area = self.scrollAreaWidgetContents
            self.files_dict = {}
            self.is_techfix = False
            self.config_data = config_data[sa_obj.action]
            valid_roles = self.config_data["validRole"]

            # Ensure only one task is selected
            if len(sa_obj.selected_ids) > 1:
                QtWidgets.QMessageBox.critical(
                    self, "Error", "Please select only one Task"
                )
                return

            # Fetch task data
            self.selected_task_data = sg_global_utils.get_entity_data(
                sg_obj, sa_obj, logger, sa_obj.entity_type
            )
            if not self.selected_task_data:
                QtWidgets.QMessageBox.critical(
                    self, "Error", "Selected task data is not found in SG"
                )
                return
            self.selected_task_data = self.selected_task_data[-1]

            # Retrieve project and task details
            self.project_name = sa_obj.project["name"]
            self.project_id = sa_obj.project["id"]
            self.selected_task_id = sa_obj.selected_ids[-1]
            self.task_fields = FIELDS["Task"]

            # Retrieve entity details
            task_entity = self.selected_task_data[self.task_fields["link"]]
            entity_filters = [
                ["code", "is", task_entity["name"]],
                ["project", "name_is", self.project_name],
            ]
            self.entity_data = sg_global_utils.get_entity_data(
                self.sg_obj,
                self.sa_obj,
                self.logger,
                task_entity["type"],
                entity_filters,
            )
            if not self.entity_data:
                QtWidgets.QMessageBox.critical(
                    self, "Error", "Selected Shot/Asset data is not found in SG"
                )
                return
            self.entity_data = self.entity_data[-1]
            self.cut_duration = self.entity_data.get(FIELDS["Shot"]["cutDuration"])

            # Extract pipeline step and status information
            self.pipeline_step = self.selected_task_data[
                self.task_fields["pipelineStep"]
            ]["name"]
            self.current_status = self.selected_task_data[self.task_fields["status"]]
            self.task_name = self.selected_task_data[self.task_fields["taskName"]]
            split_type = self.selected_task_data[self.task_fields["splitType"]]
            self.unreal_version = self.entity_data.get(FIELDS["Asset"]["unrealVersion"])

            config_task_name = self.task_name
            # Check if selected task is Techfix task
            if str(self.task_name).endswith("_TechFix"):
                self.is_techfix = True
                config_task_name = str(self.task_name).split("_", maxsplit=1)[0]

            # Check if selected task is Splitted Task
            if split_type == "SPLIT":
                config_task_name = str(self.task_name).split("_", maxsplit=1)[0]

            # Retrieve submission configuration and status mapping
            config_filter = [
                [FIELDS["CustomEntity24"]["project"], "name_is", self.project_name],
                [FIELDS["CustomEntity24"]["entityType"], "is", task_entity["type"]],
                [FIELDS["CustomEntity24"]["pathSheetName"], "is", self.pipeline_step],
                [FIELDS["CustomEntity24"]["taskName"], "is", config_task_name],
            ]
            self.task_config_data = sg_global_utils.get_entity_data(
                self.sg_obj, self.sa_obj, self.logger, "CustomEntity24", config_filter
            )

            # check if Config is empty
            if not self.task_config_data:
                QtWidgets.QMessageBox.critical(
                    None,
                    "Error",
                    "Shotgrid Config is Empty for this PipelineStep, Please check with SG Team",
                )
                return

            self.task_config_data = self.task_config_data[-1]

            self.status_config = ast.literal_eval(
                self.task_config_data[FIELDS["CustomEntity24"]["statusConfig"]]
            )
            file_configs = ast.literal_eval(
                self.task_config_data[FIELDS["CustomEntity24"]["fileConfig"]]
            )

            if not self.status_config or not file_configs:
                QtWidgets.QMessageBox.critical(
                    None,
                    "Error",
                    (
                        "Shotgrid Status/File Config is empty for this Task PipelineStep.\n"
                        "Please check with the SG Team."
                    ),
                )
                return

            self.status_config = self.status_config[self.sa_obj.action]
            self.logger.info(f"statusConfig: {self.status_config}")

            if self.current_status not in self.status_config.keys():
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    "Selected Task current status is not valid for this Action in SG",
                )
                return

            # Validate user role, assignments and start/due dates
            valid_role_assignments, valid_role_assignment_msg = (
                sg_global_utils.validate_role_assignments(
                    self.sg_obj,
                    self.sa_obj,
                    self.logger,
                    self.selected_task_data,
                    valid_roles,
                )
            )
            if not valid_role_assignments:
                QtWidgets.QMessageBox.critical(self, "Error", valid_role_assignment_msg)
                return

            is_valid_dates, dates_msg = sg_global_utils.validate_start_due_dates(
                self.logger,
                self.selected_task_data[self.task_fields["startDate"]],
                self.selected_task_data[self.task_fields["dueDate"]],
            )
            if not is_valid_dates:
                QtWidgets.QMessageBox.critical(self, "Error", dates_msg)
                return

            # Determine next status and required file configurations
            self.next_status = self.status_config[self.current_status]
            self.file_configs = file_configs.get(self.next_status, None)

            # Handle special cases for file configurations
            if not self.file_configs:
                if self.pipeline_step in ["Lighting"] and self.current_status in [
                    "movip",
                    "mvntip",
                    "qcip",
                ]:
                    self.file_configs = file_configs.get("movcpt")
                elif self.pipeline_step in ["Lighting"] and self.current_status in [
                    "sfip",
                    "sfntip",
                ]:
                    self.file_configs = file_configs.get("sfcmpt")
                else:
                    self.file_configs = file_configs.get("cmpt")

            # Clear widgets and add dynamic ones
            self.clear_widgets()
            self.add_dynamic_widget()

            # Connect UI buttons
            self.submit.clicked.connect(self.submit_files)
            self.clear.clicked.connect(self.clear_files)

            self.show()
            sys.exit(APP.exec())

        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def clear_widgets(self):
        """
        Clears the previous widgets in the scroll area.
        """
        try:
            # Clear existing widgets
            for child in self.dynamic_area.children():
                child.deleteLater()
        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def open_dialog(
        self, file_type, line_edit, selection_type, filters=None, directory=""
    ):
        """
        Opens a file/folder selection dialog based on the selection type.

        :param file_type: Type of file/folder being selected.
        :type file_type: str
        :param line_edit: QLineEdit widget to display selected file/folder path.
        :type line_edit: QtWidgets.QLineEdit
        :param selection_type: Selection mode - "File", "Files", or "Folder".
        :type selection_type: str
        :param filters: File filters (optional).
        :type filters: str, optional
        :param directory: dialog default open directory (optional).
        :type directory: str, optional
        :raises FileNotFoundError: If the selected file/folder does not exist.
        :raises Exception: If an error occurs during selection.
        """
        try:
            if selection_type == "File":
                file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self, f"Select {file_type}", directory=directory, filter=filters
                )
                if file_path:
                    if os.path.exists(file_path):
                        file_path = sg_file_operations.convert_to_unc(
                            file_path, self.logger
                        )

                        # Check for MovFile Length is matching with cutduration or not
                        if (
                            self.entity_data["type"] in ["Shot"]
                            and "Mov File" in file_type
                        ):
                            mov_properties = sg_global_utils.get_movie_properties(
                                self.logger, file_path
                            )
                            if (
                                not mov_properties
                                or mov_properties["movLength"] != self.cut_duration
                            ):
                                raise FileNotFoundError(
                                    "Frame Range is mismatched, Please check"
                                )

                        # check if attached file is correct
                        if file_type in ["Maya File", "Mov File"]:
                            prefix = self.entity_data[FIELDS["Shot"]["sceneCode"]]
                            if self.entity_data["type"] in [
                                "Shot"
                            ] and self.project_name in ["MMCH"]:
                                splits = prefix.split("_")
                                prefix = splits[0] + "_" + splits[-1]
                            if not os.path.basename(file_path).startswith(prefix):
                                raise FileNotFoundError(
                                    "Attached file is mismatched with Asset/Shot name, Please check"
                                )

                        line_edit.setText(file_path)
                        self.files_dict[file_type] = file_path
                    else:
                        raise FileNotFoundError("Selected file is not found.")

            elif selection_type == "Files":
                file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                    self, f"Select {file_type}s", directory=directory, filter=filters
                )
                if file_paths:
                    for each in file_paths:
                        if not os.path.exists(each):
                            raise FileNotFoundError("Selected file is not found.")

                        # check if attached file is correct
                        if file_type in ["Maya Files", "Mov Files"]:
                            prefix = self.entity_data[FIELDS["Shot"]["sceneCode"]]
                            if self.entity_data["type"] in [
                                "Shot"
                            ] and self.project_name in ["MMCH"]:
                                splits = prefix.split("_")
                                prefix = splits[0] + "_" + splits[-1]
                            if not os.path.basename(each).startswith(prefix):
                                raise FileNotFoundError(
                                    "Attached file is mismatched with Asset/Shot name, Please check"
                                )

                    file_paths = [
                        sg_file_operations.convert_to_unc(i, self.logger)
                        for i in file_paths
                    ]
                    self.files_dict[file_type] = file_paths
                    line_edit.setText(",".join(file_paths))
                else:
                    raise ShotgunActionException("Error in Files Selection.")

            elif selection_type == "Folder":
                folder_path = QtWidgets.QFileDialog.getExistingDirectory(
                    self, f"Select {file_type} Folder", directory=directory
                )
                if folder_path:
                    if os.path.exists(folder_path):
                        folder_path = sg_file_operations.convert_to_unc(
                            folder_path, self.logger
                        )

                        # Check if Proper unreal Folder is attached
                        if file_type in ["Unreal Folder"]:
                            ue_file = glob.glob(folder_path + "/*.uproject")
                            if not ue_file:
                                raise FileNotFoundError(
                                    "Please select Proper unreal folder."
                                )

                        line_edit.setText(folder_path)
                        self.files_dict[file_type] = folder_path
                    else:
                        raise FileNotFoundError("Selected folder is not found.")

            else:
                raise ShotgunActionException(
                    "This File/Folder type is not handled, please check with the SG Team."
                )

        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def add_dynamic_widget(self):
        """
        Adds dynamic widgets to the scroll area in the UI based on file configurations.
        """
        try:
            self.scroll_layout = QtWidgets.QVBoxLayout(self.dynamic_area)

            # Create a frame to hold the form layout
            frame = QtWidgets.QFrame()
            frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
            frame.setContentsMargins(0, 0, 0, 0)

            # Set up a form layout
            layout = QtWidgets.QFormLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)

            for label_name in self.file_configs:
                # Create widgets for each file config
                label = QtWidgets.QLabel(label_name)
                label.setObjectName(f'label_{label_name.lower().replace(" ", "_")}')
                label.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

                # Create a QFrame with QHBoxLayout for the line edit and button
                h_box_frame = QtWidgets.QFrame()
                h_box_frame.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                h_box_layout = QtWidgets.QHBoxLayout(h_box_frame)
                h_box_layout.setContentsMargins(0, 0, 0, 0)

                line_edit = QtWidgets.QLineEdit()
                line_edit.setObjectName(f'le_{label_name.lower().replace(" ", "_")}')
                line_edit.setEnabled(False)

                browse_button = QtWidgets.QPushButton("Browse")
                browse_button.setObjectName(
                    f'browse_{label_name.lower().replace(" ", "_")}'
                )
                selection_type = self.file_configs[label_name]["type"]
                filters = self.file_configs[label_name]["filter"]

                # Connect the browse button
                browse_button.clicked.connect(
                    partial(
                        self.open_dialog, label_name, line_edit, selection_type, filters
                    )
                )
                self.dynamic_line_edit_dict[label_name] = line_edit

                # Add widgets to layout
                h_box_layout.addWidget(line_edit)
                h_box_layout.addWidget(browse_button)
                layout.addRow(label, h_box_frame)

            # Add the frame to the scroll layout
            self.scroll_layout.addWidget(frame)

        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def clear_files(self):
        """
        Clears all line edits in the UI and resets the files dictionary.
        """
        try:
            for each in self.dynamic_line_edit_dict.values():
                each.clear()
            self.files_dict.clear()
        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def customized_copy(self, copy_config, source_paths, destination, ignore=None):
        """
        Renames files based on the configuration and copies them to the destination directory.
        if any folder is there in the source paths,
        it will be copied to the destination directory as well,
        without modifying anything. Files matching ignore patterns are excluded.

        :param copy_config: Dictionary containing the file copy configuration.
        :type copy_config: dict
        :param source_paths: List of source file paths.
        :type source_paths: list
        :param destination: Destination directory.
        :type destination: str
        :param ignore: List of glob patterns to ignore files/folders.
        :type ignore: list, optional
        """
        overall_status = True
        overall_msg = ""
        try:
            # Filter source_paths based on ignore patterns
            if ignore:
                filtered_paths = []
                for path in source_paths:
                    basename = os.path.basename(path)
                    if not any(
                        fnmatch.fnmatch(basename, pattern) for pattern in ignore
                    ):
                        filtered_paths.append(path)
                source_paths = filtered_paths

            file_rename_pattern = copy_config.get("fileRenamePattren", "")
            file_name = sg_global_utils.build_template_path(
                self.sg_obj,
                self.sa_obj,
                self.logger,
                file_rename_pattern,
                "<EXT>",
                self.selected_task_data,
                self.entity_data,
            )
            global_counter = 0
            extension_counter = defaultdict(int)
            destination_path = destination
            self.logger.info(f"source paths: {source_paths}")

            for each_path in source_paths:
                each_type = mimetypes.guess_type(each_path)[0]
                if os.path.isfile(each_path) and (
                    each_type.startswith("image") or each_type.startswith("video")
                    if each_type
                    else False
                ):
                    file_extension = os.path.splitext(each_path)[1][1:].lower()
                    each_item_file_name = file_name.replace("<EXT>", file_extension)

                    # replace the file name counter pace holder with the actual counter value
                    if "<COUNTER>" in file_rename_pattern:
                        ext_wise = copy_config.get("extWiseCounter", False)
                        if ext_wise:
                            extension_counter[file_extension] += 1
                            counter = extension_counter[file_extension]
                        else:
                            global_counter += 1
                            counter = global_counter

                        each_item_file_name = each_item_file_name.replace(
                            "<COUNTER>", str(counter).zfill(2)
                        )

                    # replace the file name element pace holder with the actual element value
                    if "<ELEMENT>" in file_rename_pattern:
                        element_pattern = copy_config.get("elementRegexPattren")
                        if element_pattern:
                            element = re.search(element_pattern, each_path).group(1)
                            each_item_file_name = each_item_file_name.replace(
                                "<ELEMENT>", element
                            )

                    destination_path = os.path.join(destination, each_item_file_name)

                elif os.path.isdir(each_path):
                    destination_path = os.path.join(
                        destination, os.path.basename(each_path)
                    )

                # Handle file and folder copying
                copy_status, msg = sg_file_operations.copy(
                    each_path,
                    destination_path,
                    self.logger,
                    overwrite=True,
                    buffer=25 * 1024 * 1024,
                )
                overall_status = overall_status and copy_status
                overall_msg = msg + overall_msg

        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            overall_status = False
            overall_msg = str(e)

        return overall_status, overall_msg

    def submit_files(self):
        """
        Handles the submission process for files, ensuring mandatory files are attached.

        - Disables the submit and clear buttons during processing.
        - Validates missing mandatory files.
        - Determines the correct destination for submitted files.
        - Copies files to the destination.
        - Updates version and status upon successful submission.
        """
        try:
            # Disable buttons during processing
            self.submit.setEnabled(False)
            self.clear.setEnabled(False)

            missing_files = []
            for each in self.file_configs:
                if self.file_configs[each]["mandatory"]:
                    if not self.files_dict.get(each):
                        missing_files.append(each)
                # If files are not mandatory
                else:
                    self.logger.info(
                        "Checking for Non mandatory files is attached previously"
                    )
                    if not self.files_dict.get(each):
                        workarea = self.file_configs[each].get("workarea", None)
                        self.logger.info(f"WORKAREA: {workarea}")
                        extensions = []
                        extension_filter = self.file_configs[each]["filter"]
                        # "Maya Files (*.ma);;Images (*.png*.jpg*.jpeg);;All Files (*.*)"
                        if workarea:
                            if (
                                self.file_configs[each]["type"] in ["File", "Files"]
                                and extension_filter
                            ):
                                matches = re.findall(r"\(([^)]+)\)", extension_filter)
                                for match in matches:
                                    # Find all patterns like *.ext even if they're stuck together
                                    parts = re.findall(r"\*\.[a-zA-Z0-9]+", match)
                                    for part in parts:
                                        ext = part.strip("*.")  # Remove * and .
                                        extensions.append(ext)

                            self.logger.info(f"extension: {extensions}")
                            extension = extensions[-1] if extensions else ""
                            destination = sg_global_utils.build_template_path(
                                self.sg_obj,
                                self.sa_obj,
                                self.logger,
                                self.task_config_data[
                                    FIELDS["CustomEntity24"][workarea]
                                ],
                                extensions,
                                self.selected_task_data,
                                self.entity_data,
                                is_publish=True,
                            )
                            self.logger.info(f"destination: {destination}")
                            if os.path.exists(destination):
                                if os.path.isdir(destination) and self.file_configs[
                                    each]["type"] in ["File", "Files"]:
                                    files = glob.glob(
                                        os.path.join(destination, f"*.{extension}")
                                    )

                                    if files:
                                        missing_files.append(each)
                                else:
                                    missing_files.append(each)

            if missing_files:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Missing Files",
                    f"{', '.join(missing_files)} are mandatory, please attach.",
                )
                self.submit.setEnabled(True)
                self.clear.setEnabled(True)
                return

            if (
                self.pipeline_step in ["LooknFeel", "Texture"]
                and not self.unreal_version
            ):
                slot_no = self.entity_data.get(FIELDS["Asset"]["slot"])["name"].split("-")[-1]
                self.logger.info(f"Slot: {slot_no}")
                if slot_no.isdigit() and int(slot_no) >= 218:
                    response = QtWidgets.QMessageBox.question(
                        None,
                        "Unreal Version",
                        "Is the folder from Unreal Engine 5.6?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    )
                    if response == QtWidgets.QMessageBox.Yes:
                        self.sg_obj.update(
                            self.entity_data["type"],
                            self.entity_data["id"],
                            {FIELDS["Asset"]["unrealVersion"]: "Unreal 5.6"},
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Unreal Version Error",
                            "Please convert to unreal 5.6 version and submit.",
                        )
                        return

            overall_status = True
            overall_msg = ""
            media_files_path = ""
            main_task = None
            submitted_files_list = []
            frames_pattern = None

            for each in self.file_configs:
                workarea = self.file_configs[each].get("workarea", None)
                if workarea and self.files_dict.get(each, None):
                    # get the extension of FILE type attachment,
                    # if it is FILES, destination will be directory so no need extension
                    extension = (
                        os.path.splitext(self.files_dict.get(each, ""))[1].replace(
                            ".", ""
                        )
                        if self.file_configs[each]["type"] == "File"
                        else ""
                    )
                    destination = sg_global_utils.build_template_path(
                        self.sg_obj,
                        self.sa_obj,
                        self.logger,
                        self.task_config_data[FIELDS["CustomEntity24"][workarea]],
                        extension,
                        self.selected_task_data,
                        self.entity_data,
                    )
                    # ! Anyway there will be only one thing for upload, so using this logic.
                    # ! if there are more different attachment options to upload in version,
                    # ! it will take last one.
                    media_files_path = (
                        destination
                        if self.file_configs[each].get("upload")
                        else media_files_path
                    )
                    frames_pattern = (
                        self.file_configs[each].get("copyConfig")["fileRenamePattren"]
                        if self.file_configs[each].get("upload")
                        and self.file_configs[each].get("copyConfig")
                        else frames_pattern
                    )
                    submitted_files_list.append(destination)

                    print(f"{each} is Copying, Please wait.......")
                    ignore = self.file_configs[each].get("ignore")

                    if self.file_configs[each]["type"] in ["File"]:
                        source = self.files_dict.get(each)
                        copy_status, msg = sg_file_operations.copy(
                            source,
                            destination,
                            self.logger,
                            ignores=ignore,
                            overwrite=True,
                            buffer=25 * 1024 * 1024,
                        )
                        overall_status = overall_status and copy_status
                        overall_msg = msg + overall_msg

                    elif self.file_configs[each]["type"] in ["Files"]:
                        source_files = self.files_dict.get(each)
                        customized_copy_config = self.file_configs[each].get(
                            "copyConfig"
                        )
                        if customized_copy_config:
                            copy_status, msg = self.customized_copy(
                                customized_copy_config,
                                source_files,
                                destination,
                                ignore,
                            )
                            overall_status = overall_status and copy_status
                            overall_msg = msg + overall_msg
                        else:
                            for file in source_files:
                                copy_status, msg = sg_file_operations.copy(
                                    file,
                                    destination,
                                    self.logger,
                                    buffer=25 * 1024 * 1024,
                                )
                                overall_status = overall_status and copy_status
                                overall_msg = msg + overall_msg

                    elif self.file_configs[each]["type"] in ["Folder"]:
                        source = self.files_dict.get(each)
                        customized_copy_config = self.file_configs[each].get(
                            "copyConfig"
                        )
                        if customized_copy_config:
                            source_paths = [
                                os.path.join(source, i) for i in os.listdir(source)
                            ]
                            copy_status, msg = self.customized_copy(
                                customized_copy_config,
                                source_paths,
                                destination,
                                ignore,
                            )
                            overall_status = overall_status and copy_status
                            overall_msg = msg + overall_msg
                        else:
                            source = self.files_dict.get(each, None)
                            copy_status, msg = sg_file_operations.copy(
                                source,
                                destination,
                                self.logger,
                                ignores=ignore,
                                overwrite=True,
                                buffer=25 * 1024 * 1024,
                            )
                            overall_status = overall_status and copy_status
                            overall_msg = msg + overall_msg
                    else:
                        overall_status = False
                        self.logger.warning(
                            "Unhandled file type: %s", self.file_configs[each]["type"]
                        )
                        overall_msg = (
                            "Unhandled file type, Please check with ShotGrid Team"
                        )
                else:
                    self.logger.warning("Workarea Path is not found in ShotGrid")

            if overall_status:
                # Check and update Techfix data Entry
                if self.is_techfix:
                    tech_data_filter = [
                        [
                            FIELDS["CustomEntity04"]["task"],
                            "is",
                            {"type": "Task", "id": self.selected_task_id},
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
                        QtWidgets.QMessageBox.critical(
                            None,
                            "Error",
                            "Selected Task TechFixData Record is not available in SG",
                        )
                        return
                    tech_data_entry = tech_data_entry[-1]
                    self.sg_obj.update(
                        "CustomEntity04",
                        tech_data_entry["id"],
                        {FIELDS["CustomEntity04"]["status"]: self.next_status},
                    )
                    main_task = tech_data_entry[FIELDS["CustomEntity04"]["to"]]

                # Create Version
                version_status, msg = sg_global_utils.create_version(
                    self.sg_obj,
                    self.sa_obj,
                    self.logger,
                    self.selected_task_data,
                    media_files_path,
                    submitted_files_list,
                )

                if version_status:
                    # update Task status
                    internal_version = (
                        self.selected_task_data[self.task_fields["internalVersion"]]
                        or 0
                    ) + 1
                    update_data = {
                        self.task_fields["internalVersion"]: internal_version,
                        self.task_fields["status"]: self.next_status,
                    }
                    self.sg_obj.update("Task", self.selected_task_id, update_data)

                    # for Techfix task,
                    # Please update the internal version of all fresh tasks for same department
                    # BCZ, we are allowing to raise multiple techfixes from different departments
                    # we need to keep the latest version number in remaining fresh tasks
                    # to avoid overriding of files
                    if self.is_techfix:
                        fresh_filters = [
                            [self.task_fields["project"], "name_is", self.project_name],
                            [
                                self.task_fields["pipelineStep"],
                                "name_is",
                                self.pipeline_step,
                            ],
                            [
                                self.task_fields["link"],
                                "is",
                                self.selected_task_data[self.task_fields["link"]],
                            ],
                            [self.task_fields["status"], "in", ["fsh"]],
                        ]
                        fresh_tasks = sg_global_utils.get_entity_data(
                            self.sg_obj,
                            self.sa_obj,
                            self.logger,
                            "Task",
                            filters=fresh_filters,
                        )
                        for each in fresh_tasks:
                            self.sg_obj.update(
                                "Task",
                                each["id"],
                                {self.task_fields["internalVersion"]: internal_version},
                            )

                        # update main Task also,
                        # BCZ if techfix is raised it should take latest internal version
                        if main_task:
                            self.sg_obj.update(
                                "Task",
                                main_task["id"],
                                {self.task_fields["internalVersion"]: internal_version},
                            )
                        else:
                            QtWidgets.QMessageBox.critical(
                                self,
                                "Error",
                                "Main Task of selected Techfix task is not Found in SG",
                            )

                    QtWidgets.QMessageBox.information(
                        self, "Success", "Files/Folder is succesfully submitted"
                    )
                else:
                    QtWidgets.QMessageBox.critical(self, "Error", msg)
            else:
                QtWidgets.QMessageBox.critical(self, "Error", overall_msg)

        except Exception as e:
            self.logger.error(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

        self.close()
