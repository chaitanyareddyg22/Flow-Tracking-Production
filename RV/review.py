"""
RV Review Module

Name:
    review.py
Author:
    CHAITANYA REDDY G
Created on:
    2025-09-09
Email:
    chaitanya.reddygudeti@saffronic.com
Description:
    This module provides RV review functionality for Shotgun integration.
    It enables users to approve, retake, or add notes to versions directly
    from the RV player interface. The module includes validation, permission
    checks, and status updates to ensure secure and accurate workflow management.

Classes:
    Review: Main class handling RV review operations.

Functions:
    createMode: Factory function to create a Review instance.
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import traceback
import sys
import importlib
import logging

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------
import rv.commands as rvc
import rv.extra_commands as rve
import rv.rvtypes as rvt

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------

# Configuration dictionary containing all settings for RV-Shotgrid integration
CONFIG = {
    # Shotgrid API connection details
    "shotgridUrl": "https://tmxds.shotgrid.autodesk.com",  # Base URL for Shotgrid instance
    "rvScriptName": "rvOperations",  # Name of the RV script for authentication
    "rvScriptKey": "_mowlbwcnudfin6ufrarPhkss",  # API key for RV script authentication

    # Columns to retrieve when fetching task data from Shotgrid
    "taskColumns": [
        "content", "task_assignees", "start_date", "due_date", "sg_team_lead",
        "sg_supervisor", "sg_status_list", "entity", "sg_split_type",
        "step"
    ],

    # Columns to retrieve when fetching user data from Shotgrid
    "userColumns": [
        "name", "projects", "email", "permission_rule_set"
    ],

    # Approval action permissions and valid statuses
    "approve": {
        "validRole": ["Team Lead", "Lead", "Supervisor", "Admin", "Team Lead", "Manager"],  # Roles allowed to approve
        "validLeadStatus": ["cmpt", "tlcmpt", "sfcmpt", "movcpt", "sfncpt", "mvncpt", "qccmpt", "tlapr", "movapr", "not", "sfnot", "movnot"],  # Valid task statuses for leads to approve
        "validSupStatus": ["qccmpt", "tlapr", "movapr"],  # Valid task statuses for supervisors to approve
        "validLeadVerStatus": ["rev", "tlapr", "movapr", "not", "sfnot", "movnot"],
        "validSupVerStatus": ["rev", "tlapr", "movapr"]
    },

    # Note addition permissions and valid statuses
    "note": {
        "validRole": ["Team Lead", "Lead", "Supervisor", "Admin", "Team Lead", "Manager"],  # Roles allowed to add notes
        "validLeadStatus": ["cmpt", "tlcmpt", "sfcmpt", "movcpt", "sfncpt", "mvncpt", "qccmpt", "tlapr", "movapr", "sfapr"],  # Valid task statuses for leads to add notes
        "validSupStatus": ["qccmpt", "tlapr", "movapr"],  # Valid task statuses for supervisors to add notes
        "validLeadVerStatus": ["rev", "tlapr", "movapr", "sfapr"],
        "validSupVerStatus": ["rev", "tlapr", "movapr"]
    },

    # Retake request permissions and valid statuses
    "retake": {
        "validRole": ["Supervisor", "Admin", "Manager", "Team Lead", "Lead"],  # Roles allowed to request retakes
        "validSupStatus": ["qccmpt", "tlapr", "movapr", "qcapr", "pub"],  # Valid task statuses for supervisors to request retakes
        "validLeadStatus": ["qccmpt", "tlapr", "movapr", "qcapr", "pub"],  # Valid task statuses for leads to request retakes
        "validLeadVerStatus": ["rev", "tlapr", "movapr", "qcapr"],
        "validSupVerStatus": ["rev", "tlapr", "movapr", "qcapr"]

    }
}



class Review(rvt.MinorMode):
    def __init__(self):
        """
        Initialize the Review mode for RV.

        Sets up the menu structure for review actions, initializes the logger,
        and calls the parent MinorMode initialization.

        :raises: None
        """
        rvt.MinorMode.__init__(self)
        globalBindings = None
        localBindings = [
            ('init-sg', self.initializeSgConnection, 'Initialize the ShotGrid Object'),
            ('play-start', self.show_event, 'will show rule of third grid')
            ]
        self.sgObj = None
        self.toolkitUser = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.grid_show = False

        menu = [
            ("Saffronic",
             [
                 ("Review",
                  [
                      ("Approve", self.approveVersion, None, lambda:rvc.NeutralMenuState),
                      ("Note", self.noteVersion, None, lambda:rvc.NeutralMenuState),
                      ("Retake", self.retakeVersion, None, lambda: rvc.NeutralMenuState)
                    ]
                  ),
                 ("Rule Of Third",
                  [
                      ("Show", self.show, None, lambda:rvc.NeutralMenuState),
                      ("Hide", self.hide, None, lambda: rvc.NeutralMenuState)
                    ]
                 )
                ]
            )
            ]
        self.init("Review", globalBindings, localBindings, menu)
        
        
    def show_event(self, *args):
        """
        Event handler triggered on 'play-start' binding to display Rule of Third overlay.
        
        Automatically shows the overlay for current source groups if self.grid_show is True.
        Extracts project name from media tracking info and applies white overlay.
        
        :param args: Event arguments (unused)
        """
        if self.grid_show:
            cur_source_groups = rvc.nodesOfType('RVSource')
            for each in cur_source_groups:
                group_name = rvc.nodeGroup(str(each))
                self.set_overlay_rule_of_third(group_name, "white")
                    
    def show(self, event):
        """
        Show the Rule of Third overlay via menu action.
        
        Sets self.grid_show to True and triggers the show_event handler
        to apply overlays to current sources. Displays debug feedback.
        
        :param event: Menu event (unused)
        """
        self.grid_show = True
        self.show_event(event)
            
            
    def hide(self, event):
        """
        Hide the Rule of Third overlay across all current source groups.
        
        Sets self.grid_show to False and removes overlay rectangles by setting
        their dimensions to zero.
        
        :param event: Menu event (unused)
        """
        self.grid_show = False
        cur_source_groups = rvc.nodesOfType('RVSource')
        for each in cur_source_groups:
            group_name = rvc.nodeGroup(str(each))
            self.set_overlay_rule_of_third(group_name, "white", status=False)

    @staticmethod
    def group_member_of_type(node, memberType):
        """
        Find the first node of specified type within a group.
        
        Iterates through all nodes in the group and returns the first
        matching the given memberType (e.g., 'RVOverlay').
        
        :param node: Group node name
        :type node: str
        :param memberType: Node type to find (e.g., 'RVOverlay')
        :type memberType: str
        :return: First matching node or None
        :rtype: str or None
        """        
        for n in rvc.nodesInGroup(node):
            if rvc.nodeType(n) == memberType:
                return n
        return None

    def create_overlay_rect(self, node, color, height, width, hpos, vpos):
        """
        Create rectangular overlay on RV overlay node with specified dimensions and color.
        
        Supports preset colors (red, green, blue, white). Sets up RV properties for
        width, height, color, and position.
        
        :param node: Overlay node path (e.g., 'overlay_node.rect:1')
        :type node: str
        :param color: Color key ('red', 'green', 'blue', 'white')
        :type color: str
        :param height: Rectangle height (0.0 hides)
        :type height: float
        :param width: Rectangle width (0.0 hides)
        :type width: float
        :param hpos: Horizontal position (-1.2 to 1.2 range)
        :type hpos: float
        :param vpos: Vertical position (-0.5 to 0.5 range)
        :type vpos: float
        """        
        _temp_color_dict = dict()
        _temp_color_dict['red'] = [1.0, 0.1, 0.1, 0.4]
        _temp_color_dict['green'] = [0.1, 1.0, 0.1, 0.4]
        _temp_color_dict['blue'] = [0.1, 0.1, 1.0, 0.4]
        _temp_color_dict['white'] = [1.0, 1.0, 1.0, 0.4]
        _key_colors = _temp_color_dict.keys()
        if color in _key_colors:
            _color_val = _temp_color_dict.get(color)
        else:
            _color_val = _temp_color_dict.get('green')
        
        rvc.newProperty('%s.width' % node, rvc.FloatType, 1)
        rvc.newProperty('%s.height' % node, rvc.FloatType, 1)
        rvc.newProperty('%s.color' % node, rvc.FloatType, 4)
        rvc.newProperty('%s.position' % node, rvc.FloatType, 2)

        self.set_prop('%s.width' % node, [float(width)])
        self.set_prop('%s.height' % node, [float(height)])
        self.set_prop('%s.color' % node, _color_val)
        self.set_prop('%s.position' % node, [float(hpos), float(vpos)])
    

    @staticmethod
    def set_prop(prop, value):
        """
        Set RV property value handling int/float types and list/single values.
        
        Creates property if it doesn't exist, then sets int or float property
        based on value type. Supports both single values and lists.
        
        :param prop: Full property path (e.g., 'node.width')
        :type prop: str
        :param value: Value to set (int, float, or list thereof)
        :type value: int, float, or list
        """        
        if type(value) == int or (type(value) == list and len(value) and type(value[0]) == int):
            if not rvc.propertyExists(prop):
                rvc.newProperty(prop, rvc.IntType, 1)
            rvc.setIntProperty(prop, value if (type(value) == list) else [value], True)

        elif type(value) == float or (
                type(value) == list and len(value) and type(value[0]) == float):
            if not rvc.propertyExists(prop):
                rvc.newProperty(prop, rvc.FloatType, 1)
            rvc.setFloatProperty(prop, value if (type(value) == list) else [value], True)
    

    def set_overlay_rule_of_third(self, source_group, color, status=True):
        """
        Render Rule of Third overlay grid on RV source group.
        
        Creates 4 overlay rectangles (2 horizontal, 2 vertical lines)
        forming standard Rule of Third composition guide. Shows/hides
        based on status param. Uses create_overlay_rect for each line.
        
        :param source_group: RV source group node
        :type source_group: str
        :param color: Overlay color ('white', 'red', etc.)
        :type color: str
        :param status: Show (True) or hide (False) overlay
        :type status: bool
        :default status: True
        """
        try:
            # CREATE THE OVERLAY NODE
            # ------------------------
            overlay_node = self.group_member_of_type(source_group, "RVOverlay")
            rvc.setIntProperty(overlay_node + ".overlay.show", [1], True)
            _height = 0.01 if status else 0.0
            _width = 2.4 if status else 0.0

            # MIDDLE
            # -------------
            _hpos = -1.2 if status else 0.0
            _vpos = 0.17 if status else 0.0
            self.create_overlay_rect(overlay_node + '.rect:1', color, _height, _width, _hpos, _vpos)

            # BOTTOM
            # -------------
            _hpos = -1.2 if status else 0.0
            _vpos = -0.16 if status else 0.0

            self.create_overlay_rect(overlay_node + '.rect:2', color, _height, _width, _hpos, _vpos)

            # DRAW VERTICAL LINES
            # -----------------------
            _height = 1.0 if status else 0.0
            _width = 0.01 if status else 0.0

            # LEFT SIDE
            _hpos = -0.4 if status else 0.0
            _vpos = -0.5 if status else 0.0
            self.create_overlay_rect(overlay_node + '.rect:3', color, _height, _width, _hpos, _vpos)

            # RIGHT SIDE
            _hpos = 0.39 if status else 0.0
            _vpos = -0.5 if status else 0.0
            self.create_overlay_rect(overlay_node + '.rect:4', color, _height, _width, _hpos, _vpos)

        except:
            self.logger.error(traceback.format_exc())
            rve.displayFeedback2("#### [ERROR] #### Rule of Third overlay failed to render. Check console.", 10.0)

    @staticmethod
    def validateInputData(mediaInfo, action):
        """
        Validate input data for version actions.

        :param mediaInfo: Media information dictionary
        :type mediaInfo: dict
        :param action: Action type ('approve', 'retake', 'note')
        :type action: str
        :return: Tuple of (isValid, errorMessage)
        :rtype: tuple
        """
        if not mediaInfo:
            return False, "No media information provided"

        requiredFields = ['id', 'name', 'project', 'link', 'task', 'humanUser']
        for field in requiredFields:
            if field not in mediaInfo:
                return False, f"Missing required field: {field}"

        if action not in ['approve', 'retake', 'note']:
            return False, f"Invalid action: {action}"

        return True, None

    def getTaskAndUserData(self, mediaInfo):
        """
        Retrieve task and user data from Shotgun.

        :param mediaInfo: Media information dictionary
        :type mediaInfo: dict
        :return: Tuple of (sgTaskData, sgUserData, projectData, entityData, taskData, userData)
        :rtype: tuple
        :raises Exception: If Shotgun query fails
        """
        projectData = self.parseMetadataField(mediaInfo.get('project'))
        entityData = self.parseMetadataField(mediaInfo.get('link'))
        taskData = self.parseMetadataField(mediaInfo.get('task'))

        sgTaskData = self.sgObj.find_one('Task', [['id', 'is', int(taskData['id'])]], CONFIG['taskColumns'])
        sgUserData = self.sgObj.find_one('HumanUser', [['login', 'is', self.toolkitUser]], CONFIG['userColumns'])

        return sgTaskData, sgUserData, projectData, entityData, taskData

    def validateUserPermissions(self, sgTaskData, sgUserData, action):
        """
        Validate user permissions for the action.
        
        :param sgTaskData: Shotgun task data
        :type sgTaskData: dict
        :param sgUserData: Shotgun user data
        :type sgUserData: dict
        :param action: Action type
        :type action: str
        :return: Tuple of (isValid, errorMessage)
        :rtype: tuple
        """
        userRole = sgUserData['permission_rule_set']['name']
        self.logger.info(f'userRole: {userRole}')
        self.logger.info(f'validRole: {CONFIG[action]["validRole"]}')

        if userRole not in CONFIG[action]['validRole']:
            return False, "Not a Valid Role/ Not a Valid Assigned User"

        # For production related AMIs no need to check assignments
        if userRole not in ['Admin']:
            taskArtistId = sgTaskData['task_assignees'][-1]['id'] if sgTaskData['task_assignees'] else None
            taskLeadId = sgTaskData['sg_team_lead']['id'] if sgTaskData['sg_team_lead'] else None
            taskSupId = sgTaskData['sg_supervisor']['id'] if sgTaskData['sg_supervisor'] else None

            if int(sgUserData['id']) not in [taskArtistId, taskLeadId, taskSupId]:
                return False, "You are not a valid Assignee of this Task"

            if not taskArtistId or not taskLeadId or not taskSupId:
                return False, "Artist/Lead/Supervisor is Empty for the selected Task, Please check"

        return True, None

    def getTaskConfiguration(self, sgTaskData, projectData, entityData, taskName):
        """
        Retrieve task configuration from Shotgun.

        :param sgTaskData: Shotgun task data
        :type sgTaskData: dict
        :param projectData: Project metadata
        :type projectData: dict
        :param entityData: Entity metadata
        :type entityData: dict
        :param taskName: Task name
        :type taskName: str
        :return: Status configuration dictionary
        :rtype: dict
        :raises Exception: If configuration is missing or invalid
        """
        configTaskName = taskName

        # Check if selected task is Techfix task
        if str(taskName).endswith('_TechFix'):
            configTaskName = str(taskName).split("_")[0]

        # Check if selected task is Splitted Task
        if sgTaskData['sg_split_type'] == "SPLIT":
            configTaskName = str(taskName).split("_")[0]

        # Retrieve task configuration for status mapping
        configFilter = [
            ['project', 'name_is', projectData['name']],
            ['sg_entity_type', 'is', entityData['type']],
            ['code', 'is', sgTaskData['step']['name']],
            ['sg_task_name', 'is', configTaskName]
        ]
        taskConfigData = self.sgObj.find_one('CustomEntity24', configFilter, ['sg_status_config'])

        if not taskConfigData:
            raise Exception("Shotgrid Config is Empty for this PipelineStep, Please check with SG Team.")

        statusConfig = eval(taskConfigData['sg_status_config'])

        if not statusConfig:
            raise Exception("Valid status not updated in SG Status Config, please reach out to SG team!.")

        return statusConfig

    def validateTaskStatus(self, verStatus, sgTaskData, sgUserData, action):
        """
        Validate task status for the action.

        :param verStatus: Shotgun version Status
        :type verStatus: str
        :param sgTaskData: Shotgun task data
        :type sgTaskData: dict
        :param sgUserData: Shotgun user data
        :type sgUserData: dict
        :param action: Action type
        :type action: str
        :return: Tuple of (isValid, errorMessage)
        :rtype: tuple
        """
        userRole = sgUserData['permission_rule_set']['name']
        taskStatus = sgTaskData['sg_status_list']
        taskLeadId = sgTaskData['sg_team_lead']['id'] if sgTaskData['sg_team_lead'] else None
        taskSupId = sgTaskData['sg_supervisor']['id'] if sgTaskData['sg_supervisor'] else None

        if userRole in ["Lead", "Team Lead", "Admin", "Manager"] and str(sgUserData['id']) == str(taskLeadId):
            if taskStatus not in CONFIG[action]["validLeadStatus"]:
                return False, "Task status is not valid for the Lead review"
            if verStatus not in CONFIG[action]["validLeadVerStatus"]:
                return False, "Version status is not valid for the Lead review"

        elif userRole in ["Supervisor", "Admin", "Team Lead", "Lead", "Manager"] and str(sgUserData['id']) == str(taskSupId):
            if taskStatus not in CONFIG[action]["validSupStatus"]:
                return False, "Task status is not valid for the Supervisor review"
            if verStatus not in CONFIG[action]["validSupVerStatus"]:
                return False, "Version status is not valid for the Supervisor review"

        else:
            return False, "User is not valid to review the task, Please check the Team Lead or Supervisor field and update accordingly!!"

        return True, None

    def updateRecordsInShotgun(self, taskData, versionId, projectData, dataToUpdate, isTechfix):
        """
        Update records in Shotgun.

        :param taskData: Task metadata
        :type taskData: dict
        :param versionId: Version ID
        :type versionId: int
        :param projectData: Project metadata
        :type projectData: dict
        :param dataToUpdate: Data to update
        :type dataToUpdate: dict
        :param isTechfix: Whether this is a techfix task
        :type isTechfix: bool
        :raises Exception: If techfix record is missing or update fails
        """
        # Check and update Techfix data Entry
        if isTechfix:
            techDataFilter = [
                ["sg_task", 'is', {'type': "Task", 'id': int(taskData['id'])}],
                ["project", 'is', {'type': "Project", 'id': int(projectData['id'])}]
            ]
            techDataEntry = self.sgObj.find_one('CustomEntity04', techDataFilter)

            if not techDataEntry:
                raise Exception("Selected Task TechFixData Record is not available in SG")

            self.sgObj.update('CustomEntity04', techDataEntry['id'], dataToUpdate)

        self.sgObj.update('Task', int(taskData['id']), dataToUpdate)
        self.sgObj.update('Version', versionId, dataToUpdate)

    def initializeSgConnection(self, *args):
        """
        Initialize the ShotGrid (Shotgun) connection for RV review functionality.

        This method listens for the 'sgtk-authenticated-user-changed' event and sets up
        a script-based authentication connection to ShotGrid. This approach ensures the
        plugin has full read and write access to ShotGrid fields, independent of the
        currently logged-in user's permissions.

        The connection object is stored in `self.sgObj` for use throughout the plugin.

        :raises Exception: If authentication or connection setup fails.
        """
        
        if self.sgObj:
            return

        try:
            # Import sgtk and sgtk_auth modules dynamically to avoid import issues during package loading
            if "sgtk" not in sys.modules:
                sgtk = importlib.import_module("sgtk")
            else:
                sgtk = sys.modules["sgtk"]

            if "sgtk_auth" not in sys.modules:
                sgtk_auth = importlib.import_module("sgtk_auth")
            else:
                sgtk_auth = sys.modules["sgtk_auth"]

            # Retrieve the current RV session user for toolkit authentication
            user = sgtk_auth.get_toolkit_user()
            if user:
                self.toolkitUser = str(user[0])
            else:
                rve.displayFeedback2("#### [WARNING] #### Please login to current RV session.", 10.0)
                return

            self.logger.info("DEBUG: Importing sgtk and sgtk_auth modules successful")
            self.logger.info("DEBUG: SG connection initialized")
            
            # Dynamically get ShotgunAuthenticator class from sgtk.authentication
            ShotgunAuthenticator = getattr(sgtk.authentication, "ShotgunAuthenticator")

            # Use script-based authentication for full ShotGrid access
            cdm = sgtk.util.CoreDefaultsManager()
            authenticator = ShotgunAuthenticator(cdm)

            # Create a script user with elevated permissions using configured script name and key
            user = authenticator.create_script_user(
                api_script=CONFIG["rvScriptName"],
                api_key=CONFIG["rvScriptKey"],
                host=CONFIG["shotgridUrl"]
            )

            # Set the authenticated user and establish the ShotGrid connection
            sgtk.set_authenticated_user(user)
            self.sgObj = user.create_sg_connection()

            rve.displayFeedback2("#### [SUCCESS] #### Shotgun connection initialized successfully.", 10.0)
            self.logger.info("Using sgtk script-based ShotGrid authentication for full access.")
        except Exception as e:
            error_msg = f"Failed to initialize Shotgun: {e}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            rve.displayFeedback2(f"#### [ERROR] #### {error_msg}", 10.0)

    def getCurrentVersionInfo(self):
        """
        Get current version and task info from RV session.

        This function retrieves the currently loaded media source in RV and attempts
        to extract Shotgun version and task IDs from the source metadata. The extraction
        logic may need to be customized based on how RV loads Shotgun data.

        :return: Dictionary containing media info or None if not found
        :rtype: dict or None
        :raises Exception: If there's an error accessing RV source information
        """
        try:
            # Get current frame media source from RV session
            sourceNode = rvc.sourcesAtFrame(rvc.frame())
            if not sourceNode:
                return None
            
            trackingInfoProp = "%s.tracking.info" % sourceNode[-1]
            if not rvc.propertyExists(trackingInfoProp):
                raise Exception("Not a valid ShotGrid Source Property for Review")
            
            i = iter(rvc.getStringProperty(trackingInfoProp))
            mediaInfo = dict(zip(i, i))
            return mediaInfo
        except Exception as e:
            self.logger.error(f"Failed to get current version info: {e}\n{traceback.format_exc()}")
            return None
    
    @staticmethod  
    def parseMetadataField(fieldStr):
        """
        Parse a metadata string into a dictionary with keys like 'id', 'name', and 'type'.

        The input string should be formatted as key-value pairs separated by '|',
        with each pair in the form 'key_value'. For example:
        'id_1640|name_MMCH|type_Project' → {'id': '1640', 'name': 'MMCH', 'type': 'Project'}

        This method safely handles malformed input by ignoring entries without an underscore.

        :param fieldStr: A string containing metadata in 'key_value' format separated by '|'.
        :type fieldStr: str

        :return: A dictionary mapping keys to their corresponding values.
        :rtype: dict
        """
        result = {}
        if not fieldStr:
            return result
        for item in fieldStr.split('|'):
            if '_' in item:
                key, value = item.split('_', 1)
                result[key] = value
        return result


    def approveVersion(self, *args):
        """
        Handle approve action for the current version.

        This function is called when the Approve menu item is selected. It retrieves
        the current version and task information, validates it, and updates the
        status to approved in Shotgun.

        :param args: Additional arguments (ignored)
        """
        self.handleVersionAction("approve")

    def retakeVersion(self, *args):
        """
        Handle retake action for the current version.

        This function is called when the Retake menu item is selected. It retrieves
        the current version and task information, validates it, and updates the
        status to retake in Shotgun.

        :param args: Additional arguments (ignored)
        """
        self.handleVersionAction("retake")

    def handleVersionAction(self, action):
        """
        Handle version actions: approve, retake, or note.

        This function retrieves the current version and task information,
        validates it, and updates the status in Shotgun based on the action.

        :param action: The action to perform ('approve', 'retake', or 'note')
        :type action: str
        """  
        try:
            rvc.sendInternalEvent("init-sg")
            mediaInfo = self.getCurrentVersionInfo()
            self.logger.info(f'MediaInfo: {mediaInfo}')
            if not mediaInfo:
                rve.displayFeedback2("#### [WARNING] #### No valid version/task found in current RV session.", 10.0)
                return

            updateSuccess = self.updateStatus(mediaInfo, action)
            if updateSuccess:
                feedback_messages = {
                    "approve": "#### [SUCCESS] #### Version approved successfully.",
                    "retake": "#### [SUCCESS] #### Retake requested successfully.",
                    "note": "#### [SUCCESS] #### Note added successfully."
                }
                rve.displayFeedback2(feedback_messages.get(action, "#### [SUCCESS] #### Action completed."), 10.0)
        except Exception as e:
            self.logger.error(f"{action.capitalize()} failed: {e}\n{traceback.format_exc()}")
            rve.displayFeedback2(f"#### [ERROR] #### {action.capitalize()} failed: {str(e)}", 10.0)

    def noteVersion(self, *args):
        """
        Handle note action for the current version.

        This function is called when the Note menu item is selected. It retrieves
        the current version and task information, validates it, and updates the
        status to note in Shotgun.

        :param args: Additional arguments (ignored)
        """
        self.handleVersionAction("note")

    def updateStatus(self, mediaInfo, action):
        """
        Update version and task status in Shotgun.

        This function orchestrates the status update process by validating inputs,
        checking permissions, retrieving configuration, and updating records.

        :param mediaInfo: The RV version media Tracking info
        :type mediaInfo: dict
        :param action: The action to perform ('approve', 'retake', 'note')
        :type action: str
        :return: True if update succeeded, False if validation failed
        :rtype: bool
        :raises Exception: If version/task not found or update fails
        """
        try:
            # Step 1: Validate input data
            isValid, errorMsg = self.validateInputData(mediaInfo, action)
            if not isValid:
                rve.displayFeedback2(f"#### [ERROR] #### {errorMsg}", 10.0)
                return False

            # Step 2: Get version and task information
            versionId = int(mediaInfo.get('id'))
            versionStatus = mediaInfo.get("status")

            # Step 3: Retrieve task and user data from Shotgun
            sgTaskData, sgUserData, projectData, entityData, taskData = self.getTaskAndUserData(mediaInfo)

            # Step 4: Validate user permissions
            isValid, errorMsg = self.validateUserPermissions(sgTaskData, sgUserData, action)
            if not isValid:
                rve.displayFeedback2(f"#### [ERROR] #### {errorMsg}", 10.0)
                return False

            # Step 5: Get task configuration
            taskName = taskData['name']
            statusConfig = self.getTaskConfiguration(sgTaskData, projectData, entityData, taskName)

            # Step 6: Validate task status for the action
            isValid, errorMsg = self.validateTaskStatus(versionStatus, sgTaskData, sgUserData, action)
            if not isValid:
                rve.displayFeedback2(f"#### [ERROR] #### {errorMsg}", 10.0)
                return False

            # Step 7: Prepare data for update
            taskStatus = sgTaskData['sg_status_list']
            dataToUpdate = {"sg_status_list": statusConfig[action].get(taskStatus)}
            self.logger.info(f"Data to Update: {dataToUpdate}")

            # Step 8: Determine if this is a techfix task
            isTechfix = str(taskName).endswith('_TechFix')

            # Step 9: Update records in Shotgun
            self.updateRecordsInShotgun(taskData, versionId, projectData, dataToUpdate, isTechfix)

            self.logger.info(f"Status updated to {statusConfig[action].get(taskStatus)} for version {versionId}, task {taskData['id']}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update status: {e}\n{traceback.format_exc()}")
            rve.displayFeedback2(f"#### [ERROR] #### Failed to update status: {str(e)}", 10.0)
            raise



def createMode():
    """
    Factory function to create a Review instance.

    :return: A new instance of the Review class
    :rtype: Review
    """
    return Review()


