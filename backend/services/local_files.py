"""Read local files into chat context.

Lets the assistant ingest a file the user references by path (for example an
exported CV). Plain-text formats are read directly; PDF and DOCX are supported
when the optional pypdf / python-docx packages are installed. Images are read
with on-device OCR, and (for a vision-capable model) can additionally be sent
to the model as an image so it can see the picture, not just its text.
"""

import base64
import re
from pathlib import Path
from typing import Any, Optional

from backend import config

# File paths referenced in chat, in three forms:
#  - quoted/backticked (may contain spaces): "C:\A\my file.png"
#  - unquoted ending in a file extension, allowing spaces up to that extension:
#    C:\Users\me\OneDrive - Team\Shot 2026.png
#  - UNC paths: \\server\share\file.ext
# The drive-letter rules never match URL schemes such as "https://".
_QUOTED_PATH = re.compile(
    r"""["'`]\s*([A-Za-z]:[\\/][^"'`\r\n]+|\\\\[^"'`\r\n]+?)\s*["'`]"""
)
# Lazily match from a drive letter up to the first ".ext" that is followed by a
# natural boundary (whitespace, quote, bracket, end, or trailing punctuation).
# This captures unquoted Windows paths that contain spaces.
_UNQUOTED_PATH = re.compile(
    r"""(?<![A-Za-z0-9])(
        [A-Za-z]:[\\/](?![\\/])[^\r\n"'`<>|?*]*?\.[A-Za-z0-9]{1,8}
        |
        \\\\[^\r\n"'`<>|?*]*?\.[A-Za-z0-9]{1,8}
    )(?=$|["'`\s)\]}>,;:!?]|\.\s|\.$)""",
    re.VERBOSE,
)
_HAS_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,8}$")


def extract_file_paths(text: Any) -> list[str]:
    """Extract candidate local file paths (with a file extension) from text.

    Quoted/backticked paths may contain spaces; unquoted paths stop at
    whitespace. URL schemes like ``https://`` are deliberately not matched.
    """
    raw = str(text or "")
    found: list[str] = []

    def add(candidate: str) -> None:
        cleaned = candidate.strip().strip("\"'`").rstrip(".,;:!?)]}>")
        if not cleaned or not _HAS_EXTENSION.search(cleaned):
            return
        # Skip a truncated fragment of a path already captured (e.g. an
        # unquoted match that stopped at a space inside a quoted path).
        if any(existing.startswith(cleaned) for existing in found):
            return
        if cleaned not in found:
            found.append(cleaned)

    for match in _QUOTED_PATH.findall(raw):
        add(match)
    for match in _UNQUOTED_PATH.findall(raw):
        add(match)
    return found


def find_recent_file_paths(messages: Any, max_lookback: int = 10) -> list[str]:
    """Return file paths from the most recent message that contains any.

    Lets a follow-up like "try again to read the file" reuse a path mentioned
    earlier in the conversation (by the user or quoted back by the assistant).
    """
    for msg in list(reversed(list(messages or [])))[:max_lookback]:
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if isinstance(content, str):
            paths = extract_file_paths(content)
            if paths:
                return paths
    return []


def _read_pdf(path: Path) -> tuple[bool, str]:
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return False, "PDF support unavailable: install pypdf to read PDF files."
    try:
        reader = PdfReader(str(path))
        parts = [page.extract_text() or "" for page in reader.pages]
        return True, "\n".join(parts).strip()
    except Exception as exc:
        return False, f"Failed to read PDF: {exc}"


def _read_docx(path: Path) -> tuple[bool, str]:
    try:
        import docx  # python-docx
    except Exception:
        return False, "DOCX support unavailable: install python-docx to read .docx files."
    try:
        document = docx.Document(str(path))
        return True, "\n".join(p.text for p in document.paragraphs).strip()
    except Exception as exc:
        return False, f"Failed to read DOCX: {exc}"


def _ocr_result_text(result: Any) -> str:
    text = getattr(result, "text", None)
    if text is None and isinstance(result, dict):
        text = result.get("text")
    return (text or "").strip()


def _read_image_ocr(path: Path) -> tuple[bool, str]:
    """Extract text from an image using on-device Windows OCR (winocr)."""
    if not config.WEB_OCR_ENABLED:
        return False, (
            f"{path.suffix} is an image and OCR is disabled. Export the content as "
            "PDF/text, or enable OCR (LLAMA_GUI_WEB_OCR=1)."
        )
    try:
        import winocr
        from PIL import Image
    except Exception:
        return False, (
            f"{path.suffix} is an image; OCR support is not installed. "
            "Install winocr and pillow to read text from images."
        )
    try:
        with Image.open(str(path)) as img:
            image = img.convert("RGB")
            result = winocr.recognize_pil_sync(image, config.WEB_OCR_LANG)
        return True, _ocr_result_text(result)
    except Exception as exc:
        return False, f"OCR failed: {exc}"


_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def is_image_path(path: Any) -> bool:
    return Path(str(path)).suffix.lower() in config.WEB_FILE_IMAGE_SUFFIXES


def encode_image_data_url(path: Any) -> Optional[str]:
    """Return a base64 data URL for an image, or None if it cannot be used."""
    try:
        file_path = Path(str(path)).expanduser()
    except Exception:
        return None
    if not file_path.exists() or not file_path.is_file():
        return None
    mime = _IMAGE_MIME.get(file_path.suffix.lower())
    if not mime:
        return None
    try:
        if file_path.stat().st_size > config.WEB_FILE_MAX_BYTES:
            return None
        data = base64.b64encode(file_path.read_bytes()).decode("ascii")
    except Exception:
        return None
    return f"data:{mime};base64,{data}"


def read_local_file(path: Any, max_chars: int = config.WEB_SEARCH_PAGE_CHARS) -> dict[str, Any]:
    try:
        file_path = Path(str(path)).expanduser()
    except Exception as exc:
        return {"ok": False, "error": f"Invalid path: {exc}"}

    if not file_path.exists() or not file_path.is_file():
        return {"ok": False, "error": f"File not found: {file_path}"}
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return {"ok": False, "error": f"Cannot stat file: {exc}"}
    if size > config.WEB_FILE_MAX_BYTES:
        return {"ok": False, "error": f"File too large ({size} bytes; limit {config.WEB_FILE_MAX_BYTES})."}

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        ok, text = _read_pdf(file_path)
    elif suffix == ".docx":
        ok, text = _read_docx(file_path)
    elif suffix in config.WEB_FILE_TEXT_SUFFIXES:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            ok = True
        except Exception as exc:
            ok, text = False, f"Failed to read file: {exc}"
    elif suffix in config.WEB_FILE_IMAGE_SUFFIXES:
        ok, text = _read_image_ocr(file_path)
    else:
        return {"ok": False, "error": f"Unsupported file type: {suffix or '(none)'}"}

    if not ok:
        return {"ok": False, "error": text}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "No text could be extracted from the file."}
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + f"\n\n... (truncated, {len(text)} chars total)"
    return {"ok": True, "path": str(file_path), "text": text}
