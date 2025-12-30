"""Utility functions for the CV Agent"""

import re
import pathlib
from typing import Union


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


def create_directory_with_fallback(base_path: Union[str, pathlib.Path], name: str) -> pathlib.Path:
    """
    Create a directory with fallback naming if it already exists.

    Args:
        base_path: Base directory path
        name: Desired directory name

    Returns:
        Path to the created directory
    """
    base_path = pathlib.Path(base_path)
    target_dir = base_path / name

    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    # If directory exists, add a number suffix
    counter = 1
    while True:
        numbered_dir = base_path / f"{name}_{counter}"
        if not numbered_dir.exists():
            numbered_dir.mkdir(parents=True, exist_ok=True)
            return numbered_dir
        counter += 1


def extract_company_from_url(url: str) -> str:
    """
    Extract company name from job posting URL.

    Args:
        url: Job posting URL

    Returns:
        Extracted company name or "UnknownCompany"
    """
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        # Remove www. prefix
        domain = domain.replace('www.', '')

        # Extract company name from common job site patterns
        if 'linkedin.com' in domain:
            # LinkedIn URLs often have company info, but hard to extract reliably
            return "Company"
        elif 'indeed.com' in domain:
            return "Company"
        elif 'glassdoor.com' in domain:
            return "Company"
        else:
            # For other sites, try to extract from domain
            parts = domain.split('.')
            if len(parts) >= 2:
                company_part = parts[0]
                # Capitalize first letter of each word
                return ' '.join(word.capitalize() for word in company_part.split('-'))

    except Exception:
        pass

    return "UnknownCompany"


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with optional suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add if text is truncated

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix
