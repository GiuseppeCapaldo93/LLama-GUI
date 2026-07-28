"""Shared backend configuration constants.

Keep this module free of optional third-party imports so the server can import it
during startup on a minimal Python environment.
"""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

LLAMA_DIR = ROOT_DIR / "llama"
LLAMA_BIN_DIR = LLAMA_DIR / "bin"
LLAMA_GRAMMARS_DIR = LLAMA_DIR / "grammars"
LLAMA_CUSTOM_DIR = LLAMA_DIR / "custom"
LLAMA_CUSTOM_BIN_DIR = LLAMA_CUSTOM_DIR / "bin"
LLAMA_CUSTOM_GRAMMARS_DIR = LLAMA_CUSTOM_DIR / "grammars"
MODELS_DIR = ROOT_DIR / "models"
MMPROJ_DIR = MODELS_DIR / "mmproj"
PRESETS_DIR = ROOT_DIR / "presets"
CONFIG_FILE = ROOT_DIR / "config.json"
UI_DIR = ROOT_DIR / "ui"
APP_LOGO_FILE = ROOT_DIR / "Llama-GUI Logo.png"
TOOLS_DIR = ROOT_DIR / "tools"
CLOUDFLARED_DIR = TOOLS_DIR / "cloudflared"

DEFAULT_GUI_HOST = "127.0.0.1"
DEFAULT_GUI_PORT = 5240
SUPERVISOR_RESTART_EXIT_CODE = 75
REQUEST_BODY_TIMEOUT_SECONDS = 30
MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024


def parse_gui_host(value: object, default: str = DEFAULT_GUI_HOST) -> str:
    host = str(value or "").strip()
    if not host or any(ord(ch) < 32 for ch in host) or "/" in host:
        return default
    if host == "*":
        return "0.0.0.0"
    if host.startswith("[") and host.endswith("]"):
        return host[1:-1]
    return host


def parse_gui_port(value: object, default: int = DEFAULT_GUI_PORT) -> int:
    try:
        port = int(str(value or "").strip())
    except (TypeError, ValueError):
        return default
    if port < 1 or port > 65535:
        return default
    return port


def parse_gui_allowed_hosts(value: object) -> tuple[str, ...]:
    hosts = []
    for raw_host in str(value or "").split(","):
        host = parse_gui_host(raw_host, default="")
        if host:
            host = host.lower()
        if host and host not in hosts:
            hosts.append(host)
    return tuple(hosts)


def parse_bool_env(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


GUI_HOST = parse_gui_host(os.environ.get("LLAMA_GUI_HOST"), DEFAULT_GUI_HOST)
GUI_PORT = parse_gui_port(os.environ.get("LLAMA_GUI_PORT"), DEFAULT_GUI_PORT)
GUI_ALLOWED_HOSTS = parse_gui_allowed_hosts(os.environ.get("LLAMA_GUI_ALLOWED_HOSTS"))
SUPERVISED = parse_bool_env(os.environ.get("LLAMA_GUI_SUPERVISED"))
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080

WEB_SEARCH_MAX_RESULTS = 5
WEB_SEARCH_FETCH_BYTES = 512 * 1024
WEB_SEARCH_PAGE_CHARS = 12000
WEB_SEARCH_TIMEOUT = 20
WEB_SEARCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def _first_nonempty_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return ""


def _parse_host_suffixes(value: object) -> tuple[str, ...]:
    hosts: list[str] = []
    for raw in str(value or "").replace(";", ",").split(","):
        host = raw.strip().lower().lstrip("*").strip(".")
        if host and host not in hosts:
            hosts.append(host)
    return tuple(hosts)


# Upstream proxy used to reach the public internet for web search/fetch.
# Defaults to the standard HTTP(S)_PROXY environment variables (e.g. a local
# px/cntlm forwarder). Set LLAMA_GUI_WEB_PROXY to override, or "" to disable.
WEB_SEARCH_PROXY = _first_nonempty_env(
    "LLAMA_GUI_WEB_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"
)

# Domain suffixes treated as trusted internal/intranet hosts: their private IP
# addresses are allowed (the SSRF guard is relaxed for them) and they are
# fetched directly instead of through the proxy (matching NO_PROXY behaviour).
WEB_SEARCH_INTERNAL_HOSTS = _parse_host_suffixes(
    os.environ.get("LLAMA_GUI_WEB_INTERNAL_HOSTS", "telekom.de,t-internal.com")
)

# Optional SearXNG metasearch endpoint. When set and reachable it is preferred
# over the DuckDuckGo (ddgs) backend for web searches; ddgs remains the
# fallback. Set LLAMA_GUI_SEARXNG_URL to "" to always use ddgs.
WEB_SEARCH_SEARXNG_URL = os.environ.get(
    "LLAMA_GUI_SEARXNG_URL", "http://127.0.0.1:8888"
).strip()

# Optional per-host request headers (e.g. auth cookies) applied when fetching a
# page, loaded from this JSON file at request time. Format:
#   { "decidalo.telekom.de": { "Cookie": "<your browser session cookie>" } }
WEB_AUTH_FILE = ROOT_DIR / "web_auth.json"

# Headless-browser rendering (Playwright + installed Edge). When enabled, pages
# that need JavaScript (single-page apps like decidalo) are opened in a real
# headless browser so their content actually renders before text extraction.
WEB_RENDER_ENABLED = parse_bool_env(os.environ.get("LLAMA_GUI_WEB_RENDER", "1"))
# Browser channel to drive ("msedge" reuses installed Edge and avoids a Chromium
# download; set to "" to use Playwright's bundled Chromium).
WEB_RENDER_CHANNEL = os.environ.get("LLAMA_GUI_WEB_RENDER_CHANNEL", "msedge").strip()
# Persistent browser profile directory so an interactive login survives across
# fetches (log in once, reuse the session). Gitignored.
WEB_RENDER_PROFILE_DIR = ROOT_DIR / "browser_profile"
WEB_RENDER_TIMEOUT = 45
# Extra settle time (ms) after network idle to let late XHR/templating finish.
WEB_RENDER_SETTLE_MS = 1200
# When a plain GET yields fewer than this many characters, the page is assumed
# to be a JS shell and rendering is attempted as a fallback.
WEB_RENDER_MIN_TEXT = 600
# Best-effort selectors clicked/dismissed after load (cookie banners, popups).
WEB_RENDER_DISMISS_SELECTORS = (
    "#Announcements .close",
    ".modal .close",
    "button[aria-label='Close']",
    "button:has-text('Mark as read')",
    "button:has-text('Accept')",
    "button:has-text('Akzeptieren')",
)

# Local files whose text may be read into chat context, by extension.
WEB_FILE_MAX_BYTES = 8 * 1024 * 1024
WEB_FILE_TEXT_SUFFIXES = (
    ".txt", ".md", ".markdown", ".json", ".csv", ".tsv", ".log",
    ".html", ".htm", ".xml", ".yaml", ".yml", ".rtf",
)
WEB_FILE_IMAGE_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff",
)
# On-device OCR for images/screenshots (Windows.Media.Ocr via winocr). Keeps
# image content on the machine (no cloud) - important for confidential files.
WEB_OCR_ENABLED = parse_bool_env(os.environ.get("LLAMA_GUI_WEB_OCR", "1"))
WEB_OCR_LANG = os.environ.get("LLAMA_GUI_WEB_OCR_LANG", "en").strip() or "en"

# Automatically pass a matching mmproj (multimodal projector) to llama-server so
# vision models "just work". When enabled, launching a model that has a matching
# mmproj file in models/mmproj/ (or models/) adds "-mm <path>" unless the user
# already specified an mmproj or --no-mmproj.
AUTO_MMPROJ_ENABLED = parse_bool_env(os.environ.get("LLAMA_GUI_AUTO_MMPROJ", "1"))

GITHUB_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases"
APP_REPO_URL = "https://github.com/thomas9120/LLama-GUI.git"

TUNNEL_LOG_LIMIT = 6000
PROCESS_OUTPUT_LIMIT = 5000
PROCESS_OUTPUT_TRIM = 1000

RESTART_STARTUP_DELAY_SECONDS = 2.5
RESTART_PORT_WAIT_ATTEMPTS = 10
RESTART_PORT_WAIT_SECONDS = 0.5

