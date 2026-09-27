import re
from pathlib import Path
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))


def strip_markdown(text: str | None) -> str:
    """Strip markdown headers, links, formatting and hashtags for clean preview text."""
    if not text:
        return ""
    # Remove markdown headers (#, ##, etc)
    cleaned = re.sub(r'#+\s*', '', text)
    # Remove bold / italic (*, _, **, __)
    cleaned = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', cleaned)
    # Remove markdown links [text](url) -> text
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)
    # Remove blockquotes
    cleaned = re.sub(r'>\s*', '', cleaned)
    # Remove code blocks and backticks
    cleaned = re.sub(r'`{1,3}[^`]*`{1,3}', '', cleaned)
    # Remove image tags ![alt](url)
    cleaned = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', cleaned)
    # Collapse multiple whitespaces/newlines into a single space
    cleaned = ' '.join(cleaned.split())
    return cleaned.strip()


templates.env.filters["strip_markdown"] = strip_markdown
