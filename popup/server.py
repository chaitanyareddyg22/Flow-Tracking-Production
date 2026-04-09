"""
Name:
    server.py

Author:
    CHAITANYA REDDY G

Created on:
    2026-02-24

Email:
    chaitanya.reddygudeti@saffronic.com

Description:
    This module implements a TCP server that listens for incoming notifications
    and displays them as Windows toast notifications. It also creates a system
    tray icon for the application.

    The server runs on port 5000 and listens for incoming connections. When
    data is received, it displays a toast notification using Windows 10+
    notification system.

Usage:
    Run this script directly to start the notification server:
        python server.py

    The server will run in the background as a daemon thread and can be
    stopped by clicking the 'Quit' option in the system tray icon.

Modules:
    - socket: For TCP server implementation
    - threading: For running server as daemon thread
    - logging: For debugging and error tracking
    - win11toast: For Windows toast notifications
    - pystray: For system tray icon
    - PIL: For image handling

.. note::
    This module requires Windows 10 or later for toast notifications.
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import socket
import threading
import traceback
import signal
import json
import sys
import os

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------
from win11toast import toast
import pystray
from PIL import Image

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------
from logger_setup import setup_logger

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------

#: int: TCP server port number
PORT = 5000

#: int: Buffer size for receiving data (8KB - sufficient for most notification messages)
BUFFER_SIZE = 8192

#: int: Toast notification display duration in seconds
NOTIFICATION_DURATION = 10

#: str: Notification title
NOTIFICATION_TITLE = "Flow Notification"

#: threading.Event: Event to signal server shutdown
shutdown_event = threading.Event()

#: logging.Logger: Logger instance for this module
LOGGER = setup_logger(
        logger="ServerLogger",
        log_file="D:/SG_AMI_LOG/popup/notification.log",
        use_rotating=True,
        when="D",
        interval=1,
        backup_count=7
    )


def already_running(host="127.0.0.1", port=PORT):
    """
    Check if another instance of the server is already running.

    This function attempts to connect to the specified host and port.
    If the connection is successful, it means another instance is already
    running and listening on that port.

    Parameters:
        host (str): The host address to check. Defaults to "127.0.0.1".
        port (int): The port number to check. Defaults to PORT value.

    Returns:
        bool: True if another instance is running (connection successful),
              False otherwise.

    Example:
        >>> if already_running():
        ...     print("Server already running!")
        ...     exit()
    """
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def handle_signals():
    """
    Register signal handlers for graceful shutdown.

    This function sets up handlers for SIGINT (Ctrl+C) and SIGTERM signals
    to ensure the server shuts down gracefully when terminated. When a signal
    is received, it sets the shutdown event to stop the server.

    Returns:
        None

    Example:
        >>> handle_signals()
        # Signal handlers are now registered
    """
    def _sig_handler(signum, frame):
        """Internal signal handler callback."""
        LOGGER.info(f"Signal {signum} received, shutting down...")
        shutdown_event.set()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _sig_handler)
        except Exception:
            # Signal handling may not be available on all platforms
            pass


def resource_path(rel_path: str) -> str | None:
    """
    Get the absolute path to a resource, compatible with both development and PyInstaller frozen environments.

    This function determines the base directory for resources. When the application is frozen
    by PyInstaller (especially with --onefile), it uses the _MEIPASS attribute which points to
    the temporary extraction directory. In development mode, it uses the directory of the
    current script file.

    Parameters:
        rel_path (str): The relative path to the resource file or directory.

    Returns:
        str | None: The absolute path to the resource, or None if the path is not available.
    """
    try:
        # Check if the application is frozen by PyInstaller; if so, use _MEIPASS for base path
        base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
        # Construct the full path by joining the base with the relative path
        return os.path.join(base, rel_path)
    except Exception as e:
        # Log the error for debugging purposes
        LOGGER.error(f"Error constructing resource path: {e}")
        # Return None if path is not available
        return None


def start_server():
    """
    Start the TCP server and listen for incoming notifications.

    This function creates a TCP server that binds to all available network
    interfaces on port 5000. It listens for incoming connections and
    displays Windows toast notifications when data is received.

    The server runs in an infinite loop until the shutdown event is set.
    Each incoming connection is handled in a try-except block to ensure
    the server continues running even if an error occurs.

    Returns:
        None

    Raises:
        Exception: Any exception during server operation is logged but
            not propagated to allow the server to continue running.

    Example:
        >>> start_server()
        # Server starts listening on port 5000
    """
    # toaster = ToastNotifier()
    server_socket = None
    
    # Create a custom icon for the notification to avoid using default icon
    # that may not exist in packaged distribution
    # notification_icon = create_notification_icon()

    try:
        # Create TCP socket
        # AF_INET: IPv4 address family
        # SOCK_STREAM: TCP socket type
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Allow socket to be reused (useful for rapid restarts)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to all interfaces on specified port
        server_socket.bind(("0.0.0.0", PORT))
        LOGGER.info(f"Server bound to port {PORT}")

        # Start listening for connections
        # 5: Maximum number of queued connections
        server_socket.listen(5)
        LOGGER.info(f"Server listening on 0.0.0.0:{PORT}")

        # Accept loop - runs until shutdown event is set
        while not shutdown_event.is_set():
            try:
                # Set timeout to allow checking shutdown event periodically
                server_socket.settimeout(1.0)

                try:
                    # Accept incoming connection
                    conn, addr = server_socket.accept()
                    LOGGER.info(f"Connection received from {addr}")
                except socket.timeout:
                    # Timeout is expected, continue to check shutdown event
                    continue

                # Handle the connection
                try:
                    # Receive data from client
                    # Decode bytes to string
                    data = conn.recv(BUFFER_SIZE).decode("utf-8")

                    if data:
                        # Try to parse data as JSON dict
                        try:
                            data_dict = json.loads(data)
                            
                            # Extract body from dict - try 'body' first, then 'message', then use whole dict
                            message = "\n".join(f"{k}: {v}" for k, v in data_dict.items())
                            
                            LOGGER.info(f"Displaying notification: {message}")
                        except json.JSONDecodeError:
                            # Not JSON, treat as plain string message
                            message = data
                            LOGGER.info(f"Displaying Text notification: {message}")
                        
                        # Show toast notification with proper error handling
                        try:
                            toast(
                                title=NOTIFICATION_TITLE,
                                body=message,
                                icon = resource_path("saff_icon.png"),
                                duration="long"
                            )
                            LOGGER.info("Toast notification displayed successfully")
                        except Exception as toast_error:
                            LOGGER.error(f"Error showing toast notification: {toast_error}")
                            LOGGER.debug(traceback.format_exc())
                    else:
                        LOGGER.info("Empty data received, no notification shown")
                except Exception as e:
                    # Log error during data processing
                    LOGGER.error(f"Error processing data: {e}")
                    LOGGER.debug(traceback.format_exc())
                finally:
                    # Always close the connection
                    conn.close()
                    LOGGER.debug("Connection closed")

            except Exception as e:
                # Log error but continue server loop
                LOGGER.error(f"Error in server loop: {e}")
                LOGGER.debug(traceback.format_exc())
                continue

    except Exception as e:
        # Log fatal error
        LOGGER.error(f"Fatal error in server: {e}")
        LOGGER.debug(traceback.format_exc())
    finally:
        # Cleanup: close socket if it was created
        if server_socket:
            server_socket.close()
            LOGGER.info("Server socket closed")


def run_server():
    """
    Start the notification server as a daemon thread.

    This function creates a new thread that runs the server in the
    background. The thread is set as a daemon, which means the program
    will exit when the main thread exits.

    Returns:
        None

    Example:
        >>> run_server()
        # Server starts in background thread
    """
    # Create daemon thread that runs start_server function
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    LOGGER.info("Server thread started")


def quit_app(icon, item):
    """
    Quit the application and stop the system tray icon.

    This callback function is triggered when the user clicks 'Quit'
    in the system tray menu. It stops the tray icon and sets the
    shutdown event to signal the server to stop.

    Parameters:
        icon (pystray.Icon): The system tray icon instance.
        item (pystray.MenuItem): The menu item that was clicked.

    Returns:
        None

    Example:
        >>> menu_item = pystray.MenuItem('Quit', quit_app)
        >>> # When user clicks Quit, this function is called
    """
    LOGGER.info("Quit requested from tray icon")
    shutdown_event.set()
    icon.stop()
    LOGGER.info("Application shutdown complete")


def setup_tray_icon():
    """
    Create and configure the system tray icon.

    This function loads the saff_icon.ico image and sets up
    the system tray icon with a menu containing a Quit option.

    Returns:
        pystray.Icon: The configured system tray icon.

    Example:
        >>> icon = setup_tray_icon()
        >>> icon.run()
    """
    # Load the saff_icon.png for the tray icon
    path = os.path.join(os.path.dirname(__file__), "saff_icon.ico")
    image = Image.open(path)

    # Create the quit menu item
    # Using a lambda to ensure proper callback signature
    quit_menu_item = pystray.MenuItem(
        'Quit',  # Text to display
        quit_app,  # Callback function
        default=False  # Not the default item
    )

    # Create the menu with quit option
    menu = pystray.Menu(quit_menu_item)

    # Create the tray icon with name, image, tooltip, and menu
    icon = pystray.Icon(
        "Notifier",  # Icon name
        image,  # Icon image
        "Notification Server",  # Tooltip text
        menu  # Context menu
    )

    LOGGER.info("Tray icon configured")
    return icon


def watch_shutdown(icon):
    """
    Monitor the shutdown event and stop the tray icon when signaled.

    This function runs in a separate thread and waits for the shutdown
    event to be set. Once set, it attempts to stop the tray icon gracefully.

    Parameters:
        icon (pystray.Icon): The system tray icon instance to stop.

    Returns:
        None

    Example:
        >>> icon = setup_tray_icon()
        >>> threading.Thread(target=watch_shutdown, args=(icon,), daemon=True).start()
    """
    while not shutdown_event.is_set():
        shutdown_event.wait(1)

    try:
        icon.stop()
    except Exception:
        pass


def main():
    """
    Main entry point for the notification server application.

    This function initializes logging, starts the TCP server in a
    background thread, creates the system tray icon, and runs it.

    Returns:
        None

    Example:
        >>> main()
        # Application starts with server and tray icon
    """

    # Register signal handlers for graceful shutdown
    handle_signals()

    LOGGER.info("=" * 50)
    LOGGER.info("Starting Notification Server")
    LOGGER.info("=" * 50)
    
    if already_running():
        LOGGER.info(f"Another instance is already running. Exiting.")
        return

    # Start the TCP server in background thread
    run_server()

    # Setup the system tray icon
    tray_icon = setup_tray_icon()

    # Start a daemon thread to watch for shutdown event
    threading.Thread(target=watch_shutdown, args=(tray_icon,), daemon=True).start()

    # Run the tray icon
    tray_icon.run()


# --------------------------------------------------------------------------------------------------
# Module Execution
# --------------------------------------------------------------------------------------------------

# Check if this script is run directly (not imported)
if __name__ == "__main__":
    main()
