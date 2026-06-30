"""
Input Processing Engine — Excel parsing & GitHub URL validation.
Accepts Excel files with GitHub repository links, validates them,
and queues repositories for analysis.
"""
import re
import logging
from pathlib import Path
from typing import List, Tuple
import openpyxl

logger = logging.getLogger(__name__)

# Regex pattern for GitHub repository URLs
GITHUB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9\-_.]+)/([a-zA-Z0-9\-_.]+)/?(?:\.git)?$"
)


def parse_github_url(url: str) -> Tuple[str, str] | None:
    """
    Extract owner and repo name from a GitHub URL.
    Returns (owner, repo) tuple or None if invalid.
    """
    url = url.strip().rstrip("/")
    # Remove .git suffix if present
    if url.endswith(".git"):
        url = url[:-4]
    match = GITHUB_URL_PATTERN.match(url)
    if match:
        return match.group(1), match.group(2)
    return None


def validate_github_url(url: str) -> bool:
    """Check if a string is a valid GitHub repository URL."""
    return parse_github_url(url) is not None


def parse_excel_file(file_path: str) -> List[dict]:
    """
    Parse an Excel file containing GitHub repository links.
    Searches all columns for GitHub URLs.
    
    Returns a list of dicts: [{"url": "...", "owner": "...", "name": "..."}]
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    repos = []
    seen_urls = set()

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            for cell_value in row:
                if cell_value is None:
                    continue
                cell_str = str(cell_value).strip()
                if not cell_str:
                    continue

                # Check if cell contains a GitHub URL
                parsed = parse_github_url(cell_str)
                if parsed:
                    owner, name = parsed
                    normalized_url = f"https://github.com/{owner}/{name}"

                    if normalized_url not in seen_urls:
                        seen_urls.add(normalized_url)
                        repos.append({
                            "url": normalized_url,
                            "owner": owner,
                            "name": name,
                        })
                        logger.info(f"Found repo: {owner}/{name}")

    wb.close()
    logger.info(f"Parsed {len(repos)} unique repositories from {file_path}")
    return repos


def parse_text_urls(text: str) -> List[dict]:
    """
    Parse GitHub URLs from raw text (comma, newline, or space separated).
    Useful for single URL input or pasting multiple URLs.
    """
    repos = []
    seen_urls = set()
    
    # Split by common delimiters
    potential_urls = re.split(r"[,\n\r\s]+", text.strip())
    
    for url_str in potential_urls:
        url_str = url_str.strip()
        if not url_str:
            continue
        parsed = parse_github_url(url_str)
        if parsed:
            owner, name = parsed
            normalized_url = f"https://github.com/{owner}/{name}"
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                repos.append({
                    "url": normalized_url,
                    "owner": owner,
                    "name": name,
                })

    return repos
