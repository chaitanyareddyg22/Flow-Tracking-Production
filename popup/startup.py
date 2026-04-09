"""
Name:
    startup.py

Author:
    CHAITANYA REDDY G

Created on:
    2026-02-26

Email:
    chaitanya.reddygudeti@saffronic.com

Description:
    This module provides functionality to create Windows startup shortcuts.
    It allows applications to automatically start when a user logs into
    Windows by creating a shortcut in the user's Startup folder.
    
    The module uses Windows COM objects (WScript.Shell) to create and
    manage .lnk shortcut files with configurable properties such as
    target path, arguments, working directory, and icon.
    
    This is particularly useful for desktop applications that need to
    run automatically on system startup, such as notification servers,
    background services, or utility applications.

Usage:
    Create a startup shortcut for an application:
        >>> from server_to_startup import ensure_startup_shortcut
        >>> ensure_startup_shortcut(
        ...     logger=logger,
        ...     app_name="MyApplication"
        ... )
    
    The shortcut will be created in the user's Startup folder:
    %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

Requirements:
    - Windows operating system
    - pywin32 (for win32com.client)
    - pathlib (Python standard library)

.. note::
    This module only works on Windows systems and requires the pywin32
    package to be installed.
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import os
import subprocess
from pathlib import Path

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------
import win32com.client

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
from .server import already_running

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Global Variables
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------

#: str: Path to the Windows Startup folder (user-specific)
# This folder contains shortcuts that Windows executes when the user logs in
STARTUP_FOLDER_PATH = r"Microsoft\Windows\Start Menu\Programs\Startup"

#: str: Default server executable name for startup shortcut
SERVER_EXE = "W:\shotgrid\sgRepo311\popup\exe\server.exe"


def ensure_startup_shortcut(logger, app_name: str = "NotificationServer") -> bool:
    """
    Create or update a Windows startup shortcut for the specified application.
    
    This function creates a Windows shortcut (.lnk file) in the user's Startup
    folder. If a shortcut with the specified app_name already exists, it will
    be updated only if the target path has changed. If the shortcut already
    matches the specified parameters, no action is taken.
    
    The function uses Windows COM objects (WScript.Shell) to create the shortcut
    with various configurable properties including target path, working directory,
    and application icon.
    
    Parameters:
        logger: Logger instance for logging details and errors. This is a required parameter.
            
        app_name (str, optional): The name of the application, used as the
            base name for the shortcut file (without extension). This name
            appears in the Startup folder and in the task manager.
            Defaults to "MyApp". Example: "NotificationServer"

    Returns:
        bool: Returns True if a new shortcut was created or an existing shortcut
            was updated. Returns False if a shortcut already exists with the
            exact same target path (no update needed).

    Raises:
        FileNotFoundError: If the specified executable path does not exist.
        OSError: If unable to access the Startup folder or create the shortcut.
        com_error: If Windows COM operations fail.

    Example:
        Create a basic startup shortcut with logger:
        >>> from logger_setup import setup_logger
        >>> logger = setup_logger()
        >>> ensure_startup_shortcut(logger)
        True
        
        Create a named shortcut:
        >>> ensure_startup_shortcut(
        ...     logger,
        ...     app_name="NotificationServer"
        ... )
        True
        
        Updating an existing shortcut (returns False if unchanged):
        >>> ensure_startup_shortcut(logger, "MyApp")
        False
        
    Note:
        - The executable path is derived from the global variable SERVER_EXE
        - The shortcut target path uses SERVER_EXE as the executable
        - The shortcut is created in the current user's Startup folder only
        - The shortcut runs with the current user's privileges
        - If the executable is moved or renamed, the shortcut will need to be
          recreated
    """
    
    # ------------------------------------------------------------------------------------------------
    # Resolve the executable path to an absolute path
    # This ensures we have the full path regardless of how the exe_path was provided
    # ------------------------------------------------------------------------------------------------
    exe_path = str(Path(SERVER_EXE).resolve())
    
    # Verify the executable file exists before creating the shortcut
    if not Path(exe_path).exists():
        error_msg = f"Executable not found: {exe_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    logger.info(f"Executable found at: {exe_path}")
    
    
    # ------------------------------------------------------------------------------------------------
    # Check if server is already running
    # ------------------------------------------------------------------------------------------------
    if not already_running():
        try:
            # Start the server process
            # Using DETACHED_PROCESS to run it in the background
            subprocess.Popen(
                [exe_path],
                cwd=str(Path(exe_path).parent),
                creationflags=subprocess.DETACHED_PROCESS
            )
            logger.info(f"Server started successfully")
        except Exception as e:
            error_msg = f"Failed to start server: {e}"
            logger.error(error_msg)
            print(error_msg)
            input("check above error")
            raise RuntimeError(error_msg) from e
    
    try:
        # Construct the path to the user's Startup folder
        # os.environ["APPDATA"] points to the current user's AppData\Roaming folder
        startup = Path(os.environ["APPDATA"]) / STARTUP_FOLDER_PATH
        
        # Define the full path for the shortcut file (.lnk extension)
        # The shortcut will be named {app_name}.lnk in the Startup folder
        lnk = startup / f"{app_name}.lnk"
        
        logger.info(f"Startup folder path: {startup}")
        logger.info(f"Shortcut path: {lnk}")

        # Create a Windows Shell object to work with shortcuts
        # WScript.Shell provides COM interface for creating Windows shortcuts
        shell = win32com.client.Dispatch("WScript.Shell")
        
        # ------------------------------------------------------------------------------------------------
        # Check if shortcut already exists
        # If it exists, verify if the target path matches
        # If it matches exactly, there's no need to update the shortcut
        # ------------------------------------------------------------------------------------------------
        if lnk.exists():
            # Load the existing shortcut to check its properties
            sc = shell.CreateShortCut(str(lnk))
            
            # Compare the existing shortcut's target path with the requested path
            # Both paths are resolved to absolute paths for accurate comparison
            existing_target = Path(sc.TargetPath).resolve()
            new_target = Path(exe_path).resolve()
            
            # If both target path match, return False (no update needed)
            if existing_target == new_target:
                logger.info(f"Shortcut already exists and matches - no update needed for: {app_name}")
                print(f"Shortcut already exists and matches - no update needed for: {app_name}")
                return True  # Server started and shortcut already correct
        
        # ------------------------------------------------------------------------------------------------
        # Create or update the shortcut
        # This section executes if:
        #   - No shortcut exists, OR
        #   - Shortcut exists but target is different
        # ------------------------------------------------------------------------------------------------
        
        # Create a new shortcut object
        sc = shell.CreateShortCut(str(lnk))
        
        # Set the target path - the executable that will run on startup
        sc.TargetPath = exe_path
        
        # Set the working directory - where the application will run from
        # Using the parent directory of the executable
        sc.WorkingDirectory = str(Path(exe_path).parent)
        
        # Set the icon for the shortcut
        # Using the executable's own icon (first icon in the executable)
        sc.IconLocation = exe_path
        
        # Set the window style
        # 1 = Normal window (SW_SHOWNORMAL) - the application opens normally
        # Other options: 3 = Maximized (SW_SHOWMAXIMIZED), 7 = Minimized (SW_SHOWMINNOACTIVE)
        sc.WindowStyle = 1  # Normal window
        
        # Save the shortcut to disk
        # This writes the .lnk file to the Startup folder
        sc.save()

        logger.info(f"Successfully created/updated startup shortcut for: {app_name}")
        print(f"Successfully created/updated startup shortcut for: {app_name}")
        logger.info(f"Executable path: {exe_path}")

        return True
    
    except Exception as e:
        error_msg = f"Unexpected error creating startup shortcut: {e}"
        logger.error(error_msg)
        input("check above error")
        print(error_msg)
