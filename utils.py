"""Utility functions for the CV Agent"""

import re


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string to be used as a filename.

    Args:
        filename: The filename to sanitize

    Returns:
        A sanitized filename safe for filesystem use
    """
    if not filename:
        return "unknown"

    # Replace invalid characters with underscores
    # Invalid characters: < > : " | ? * \ / and control characters
    invalid_chars = r'[<>:"|?*\\/]'
    sanitized = re.sub(invalid_chars, '_', filename)

    # Replace multiple consecutive underscores with single underscore
    sanitized = re.sub(r'_+', '_', sanitized)

    # Remove leading/trailing underscores and whitespace
    sanitized = sanitized.strip('_ \t\n\r')

    # Ensure it's not empty
    if not sanitized:
        return "unknown"

    # Limit length to reasonable filename length
    if len(sanitized) > 100:
        sanitized = sanitized[:97] + "..."

    return sanitized


