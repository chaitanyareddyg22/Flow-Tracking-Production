"""
Name: 
    client.py

Author:
    CHAITANYA REDDY G

Created on:
    2026-02-24

Email:
    chaitanya.reddygudeti@saffronic.com

Description:
    This module provides a client for sending notifications to the popup server.
    It establishes a TCP connection to the server and sends messages that are
    then displayed as Windows toast notifications.
    
    The client supports sending both string messages and dictionary messages.
    Dictionary messages are automatically serialized to JSON format before sending.

Usage:
    Send a string notification:
        >>> send_notification("Hello from Client!", "127.0.0.1", 5000)
    
    Send a dictionary notification:
        >>> message = {"title": "Task Complete", "body": "Your render is finished"}
        >>> send_notification(message, "127.0.0.1", 5000)

Requirements:
    - Python 3.6+
    - A running instance of server.py or test.py

.. note::
    The server must be running before sending notifications.
"""

# --------------------------------------------------------------------------------------------------
# Python built-in modules import
# --------------------------------------------------------------------------------------------------
import socket
import json
import traceback

# --------------------------------------------------------------------------------------------------
# Third-party modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Saffronic modules import
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------------------------

#: int: Default TCP port for the notification server
DEFAULT_PORT = 5000

#: str: Default host address (localhost)
DEFAULT_HOST = "127.0.0.1"


def send_notification(logger, message, host, port=DEFAULT_PORT):
    """
    Send a notification message to the popup server.
    
    This function establishes a TCP connection to the specified server
    and sends the message. If the message is a dictionary, it is automatically
    converted to a JSON string before sending.
    
    Args:
        message (str or dict): The notification message to send.
            Can be either:
            - A string message that will be sent directly
            - A dictionary that will be serialized to JSON string
        host (str): The server hostname or IP address.
            For local testing, use "127.0.0.1" or "localhost".
        port (int, optional): The server port number. Defaults to 5000.
            Must match the port the server is listening on.
    
    Returns:
        None
    
    Raises:
        ConnectionRefusedError: If unable to connect to the server.
        OSError: For socket-related errors.
    
    Example:
        Sending a string message:
        >>> send_notification("Task completed successfully!", "127.0.0.1")
        
        Sending a dictionary message:
        >>> msg = {"title": "Render Done", "message": "Animation render finished"}
        >>> send_notification(msg, "127.0.0.1", 5000)
        
        Using custom host and port:
        >>> send_notification("Alert!", "192.168.1.100", 5001)
    """
    # Create a TCP socket (IPv4 address family, stream socket)
    # AF_INET: IPv4 address family
    # SOCK_STREAM: TCP socket type (reliable, connection-oriented)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logger.info(host)
    logger.info(type(host))
    logger.info(port)
    logger.info(message)
    
    try:
        # Establish connection to the server
        # Connect to the specified host and port
        client.connect((host, port))
        
        # Convert message to string if it's a dictionary
        # This allows flexible message passing - both dict and str types supported
        if isinstance(message, dict):
            # Serialize dictionary to JSON string for structured data transfer
            message = json.dumps(message)
        
        # Encode the message to bytes (UTF-8 encoding)
        # This is required because socket.send() expects bytes, not strings
        # Using "utf-8" ensures proper encoding of special characters
        client.send(message.encode("utf-8"))
        
    except Exception as e:
        # Log the error for debugging purposes
        # This helps identify connection issues
        logger.error(f"Error sending notification: {e}")
        logger.error(traceback.format_exc())
        
    finally:
        # Always close the client socket to release network resources
        # This ensures proper cleanup regardless of whether send succeeded or failed
        logger.info("closing connection")
        client.close()


# --------------------------------------------------------------------------------------------------
# Module Execution
# --------------------------------------------------------------------------------------------------

# Example usage demonstrating how to use the send_notification function
# These examples show both string and dictionary message formats

# if __name__ == "__main__":
    # Example 1: Sending a simple string message
    # This is the most basic usage - just provide the message and host
    # send_notification("Hello from Client 1!", "BGINCHAMPC02424")
    
    # Example 2: Sending a dictionary as a message
    # Dictionaries are automatically converted to JSON strings
    # import logging as logger
    
    # message = {"title": "Notification", "body": "This is a test message"}
    # send_notification(logger, message, "BGINCHAMPC02401")
    
    # Example 3: Using custom portc
    # Useful when server is running on a non-default port
    # send_notification("Custom port message", DEFAULT_HOST, 5001)
