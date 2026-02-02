"""
Name:
    sg_file_operations.py
Author:
    CHAITANYA REDDY G
Created on:
    2025-03-28
Email:
    chaitanya.reddygudeti@saffronic.com
Description:
    This Module is used to Handle the File Operations
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import pathlib
import traceback
import shutil
import os
import json

# import base64
# import sqlite3
import stat
import win32wnet
import win32api
import win32con

import win32security

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------
with open(
    os.path.join(os.path.dirname(__file__), "config\\action_menu_config.json"),
    "r",
    encoding="utf-8",
) as CNFG:
    CONFIG_DATA = json.load(CNFG)


# pylint: disable=broad-except
def impersonate(func):
    """
    Decorator to impersonate a logged-on user while executing the wrapped function.

    :param func: The function to execute with impersonated credentials.
    :type func: Callable
    """

    def wrapper_func(*args, **kwargs):
        login = password = ""
        conn = None
        handle = None
        result = None

        # Step 1: Fetch credentials from DB
        try:
            # dbFile = CONFIG_DATA['dbFilePath']
            # conn = sqlite3.connect(dbFile)
            # cursor = conn.execute("SELECT name, pwsd FROM SCRIPT_USER")
            # rows = cursor.fetchall()
            # if not rows:
            #     print("No script user found in DB.")
            #     return func(*args, **kwargs)

            # Use the last user record
            # login = base64.b64decode(rows[-1][0]).decode('ascii')
            # password = base64.b64decode(rows[-1][1]).decode('ascii')

            login = ""
            password = ""

        except Exception as e:
            print("Error during DB operation:", traceback.format_exc())
            print(e)
            return func(*args, **kwargs)

        finally:
            if conn:
                conn.close()

        # Step 2: Impersonate and execute the function
        if login and password:
            try:
                if os.getenv("USERDOMAIN") in ["TECHMAHINDRA"]:
                    handle = win32security.LogonUser(
                        login,
                        None,  # win32api.GetDomainName()
                        password,
                        win32con.LOGON32_LOGON_NEW_CREDENTIALS,
                        win32con.LOGON32_PROVIDER_WINNT50,
                    )
                else:
                    handle = win32security.LogonUser(
                        login,
                        win32api.GetDomainName(),
                        password,
                        win32con.LOGON32_LOGON_INTERACTIVE,
                        win32con.LOGON32_PROVIDER_DEFAULT,
                    )
                win32security.ImpersonateLoggedOnUser(handle)
                result = func(*args, **kwargs)

            except Exception:
                print("Error during impersonation:", traceback.format_exc())

            finally:
                try:
                    if handle:
                        win32security.RevertToSelf()
                        handle.Close()
                except Exception:
                    print("Error during cleanup:", traceback.format_exc())
        else:
            print("Login or Password is empty, So skipping Impersonation.")
            result = func(*args, **kwargs)

        return result

    return wrapper_func


@impersonate
def copy(
    source,
    destination,
    logger,
    ignores=None,
    overwrite=False,
    buffer=16 * 1024,
    metadata=True,
):
    """
    Copies files or directories from the source to the destination with customizable options.

    :param source: Path to the source file or directory.
    :type source: str
    :param destination: Path to the destination file or directory.
    :type destination: str
    :param logger: Logger object to log messages.
    :type logger: logging.Logger
    :param ignores: Patterns to ignore during the copy process, defaults to None.
    :type ignores: list or None, optional
    :param overwrite: If True, overwrites the destination if it exists, defaults to False.
    :type overwrite: bool, optional
    :param buffer: Buffer size for file copying, defaults to 16*1024.
    :type buffer: int, optional
    :param metadata: If True, preserves file metadata, defaults to True.
    :type metadata: bool, optional
    :raises ValueError: If the source path doesn't exist or if source and 
    destination are incompatible.
    :return: True if the copy operation was successful, False otherwise.
    :rtype: bool
    """
    status = False
    msg = ""
    try:
        logger.info(f"Source: {source}")
        logger.info(f"Destination: {destination}")

        source = convert_to_unc(source, logger)
        destination = convert_to_unc(destination, logger)

        source_path = pathlib.Path(source)
        destination_path = pathlib.Path(destination)

        # Check and raise Exception if Source does not exist
        if not source_path.exists():
            msg = msg + "Source path does not exist."
            logger.error(msg)
            raise ValueError(msg)

        copy_func = shutil.copy2 if metadata else shutil.copy

        # Improve copy speed using a custom buffer
        def _copy_file_obj(fsrc, fdst, length=buffer):
            """Copy data from file-like object fsrc to file-like object fdst"""
            while True:
                buf = fsrc.read(length)
                if not buf:
                    break
                fdst.write(buf)

        shutil.copyfileobj = _copy_file_obj

        # Ignore patterns if provided
        ignore_func = shutil.ignore_patterns(*ignores) if ignores else None

        # Handle existing destination
        if destination_path.exists():
            if not overwrite:
                msg = msg + "Destination already exists. Overwrite is set to False."
                logger.error(msg)
                raise ValueError(msg)

            # Check the access of file/folder and make it writable if it's not
            if not os.access(destination_path, os.W_OK):
                original_mode = stat.S_IMODE(destination_path.stat().st_mode)
                destination_path.chmod(original_mode | stat.S_IWRITE)

            if source_path.is_file():
                copy_func(source, destination)
                status = True
            else:
                shutil.rmtree(destination)
                shutil.copytree(source, destination, ignore=ignore_func)
                status = True

            # restore the original mode of destination, if it is modified
            if "originalMode" in locals():
                destination_path.chmod(original_mode)

        # Handle non-existent destination
        else:
            if source_path.is_file():
                if destination_path.suffix:
                    destination_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    destination_path.mkdir(parents=True, exist_ok=True)
                copy_func(source, destination)
                status = True
            else:
                if destination_path.is_file():
                    msg = (
                        msg
                        + "Source is a directory and destination is a file. Please check."
                    )
                    logger.error(msg)
                    raise ValueError(msg)
                else:
                    shutil.copytree(source, destination, ignore=ignore_func)
                    status = True

    except Exception as e:
        msg = str(e)
        logger.error(f"An error occurred: {str(e)}")
        logger.error(traceback.format_exc())

    return status, msg


@impersonate
def delete_path(path, logger):
    """
    Deletes a file or folder after converting the path to UNC format.
    Logs the deletion process, handles exceptions, and ensures proper error tracking.

    :param path: Path to the file or folder to be deleted.
    :type path: str or pathlib.Path
    :param logger: Logger instance to record events.
    :type logger: logging.Logger
    """
    status = False
    try:
        # Log the initial path information
        logger.info(f"Attempting to delete: {path}")

        # Convert path to a UNC format (ensure convertToUNC is implemented correctly)
        path = pathlib.Path(convert_to_unc(path, logger))

        if path.is_file():
            # Delete file
            path.unlink()
            logger.info(f"File deleted successfully: {path}")
            status = True
        elif path.is_dir():
            # Delete folder and its contents
            shutil.rmtree(str(path))
            logger.info(f"Folder deleted successfully: {path}")
            status = True
        else:
            # Log warning if the path doesn't exist
            logger.warning(f"Path does not exist: {path}")

    except PermissionError:
        # Handle permission errors separately
        logger.error(f"Permission denied while deleting {path}. Check access rights.")
    except FileNotFoundError:
        # Handle missing files/folders gracefully
        logger.error(f"File/Folder not found: {path}. Nothing to delete.")
    except Exception as e:
        # Log the full traceback for debugging unexpected errors
        logger.exception(f"Unexpected error while deleting {path}: {str(e)}")

    return status


def convert_to_unc(path, logger):
    """
    Converts a mapped drive path to its corresponding UNC path.

    :param path: The path with a mapped drive letter (e.g., "Z:\\folder\\file.txt").
    :type path: str
    :param logger: Logger object to log messages.
    :type logger: logging.Logger
    :return: The UNC path (e.g., "\\\\server\\share\\folder\\file.txt").
    :rtype: str
    :raises Exception: If the conversion to UNC fails.
    """
    try:
        # Split the drive letter and the rest of the path
        if path[1] in [":"] and path[0] not in ["c", "C", "d", "D"]:
            path = path.replace("\\", "/")
            drive, tail = os.path.splitdrive(path)
            if not drive:
                raise ValueError(
                    "Invalid mapped drive path. Ensure the path includes a drive letter."
                )

            # Use win32wnet to get the UNC path for the drive
            # pylint: disable=c-extension-no-member
            unc_drive = win32wnet.WNetGetUniversalName(drive).replace("\\", "/")

            # Combine the UNC drive with the remaining path
            path = os.path.join(unc_drive, tail.lstrip("/")).replace("\\", "/")
    except Exception as e:
        drive, tail = os.path.splitdrive(path)
        if drive == "J:":
            path = os.path.join(
                "//saffstorage03/saffstoran/Disney/MMCH", tail.lstrip("/")
            ).replace("\\", "/")
        logger.error(f"Failed to convert to UNC. Error: {str(e)}")
        logger.error(traceback.format_exc())
    return path
