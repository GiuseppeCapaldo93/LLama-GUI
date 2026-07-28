"""Chat proxy helpers."""

import functools
import ipaddress
import re
import socket
from typing import Any, Mapping, Sequence

from backend import config


def attach_images_to_last_user_message(
    messages: Sequence[Mapping[str, Any]], image_data_urls: Sequence[str]
) -> list[dict[str, Any]]:
    """Attach base64 image data URLs to the most recent user message.

    Converts that message's content into the OpenAI multimodal parts format so a
    vision-capable llama-server can see the image(s) alongside the text.
    """
    result = [dict(msg) for msg in messages]
    if not image_data_urls:
        return result
    for idx in range(len(result) - 1, -1, -1):
        if result[idx].get("role") != "user":
            continue
        content = result[idx].get("content", "")
        if isinstance(content, list):
            parts = list(content)
        elif content:
            parts = [{"type": "text", "text": content}]
        else:
            parts = []
        for url in image_data_urls:
            parts.append({"type": "image_url", "image_url": {"url": url}})
        result[idx]["content"] = parts
        break
    return result


def get_latest_user_message(messages: Sequence[Mapping[str, Any]]) -> str:
    for msg in reversed(messages or []):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content.strip()
    return ""


def build_search_queries(user_text: Any) -> list[str]:
    query = re.sub(r"\s+", " ", str(user_text or "").strip())
    if len(query) > 180:
        query = query[:180].rsplit(" ", 1)[0]
    return [query] if query else []


_URL_PATTERN = re.compile(r"https?://[^\s`'\"<>]+", re.IGNORECASE)


def extract_urls(text: Any) -> list[str]:
    """Extract http(s) URLs from free text.

    Stops at whitespace and common wrapping characters (backticks, quotes,
    angle brackets) so a URL pasted as `url`, "url", or <url> is captured
    cleanly, and trims trailing sentence punctuation.
    """
    urls: list[str] = []
    for match in _URL_PATTERN.findall(str(text or "")):
        cleaned = match.rstrip(".,;:!?)]}>`'\"")
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return urls


def find_recent_urls(messages: Sequence[Mapping[str, Any]], max_lookback: int = 10) -> list[str]:
    """Return URLs from the most recent conversation message that contains any.

    Scans newest-first (across user and assistant messages) so a follow-up like
    "try again" can reuse a link mentioned earlier in the chat when the current
    message itself has no URL.
    """
    for msg in list(reversed(messages or []))[:max_lookback]:
        content = msg.get("content", "")
        if isinstance(content, str):
            urls = extract_urls(content)
            if urls:
                return urls
    return []


_REFERENCE_HINTS = (
    "again",
    "retry",
    "the page",
    "that page",
    "this page",
    "the site",
    "the website",
    "that website",
    "the url",
    "that url",
    "the link",
    "that link",
    "the content",
    "the file",
    "that file",
    "this file",
    "the screenshot",
    "that screenshot",
    "the image",
    "that image",
    "the picture",
    "the document",
    "the pdf",
    "the cv",
    "my profile",
    "my cv",
    "fetch it",
    "fetch the",
    "retrieve it",
    "retrieve the",
    "read it",
    "read the",
    "same url",
    "same link",
    "same page",
    "load it",
    "open it",
    "view it",
    "look at it",
)


def references_previous_page(text: Any) -> bool:
    """Heuristic: does a URL-less message refer back to a page mentioned earlier?

    Used to decide whether a follow-up such as "could you try again?" or "read
    the page" should reuse an earlier link instead of running a fresh text
    search. Plain questions with no such reference fall through to search.
    """
    low = str(text or "").lower()
    return any(hint in low for hint in _REFERENCE_HINTS)


def build_search_context(
    search_results: Sequence[Mapping[str, Any]],
    fetched_pages: Mapping[str, Mapping[str, Any]],
    max_source_chars: int = 3500,
):
    sources = []
    context_parts = []
    for idx, result in enumerate(search_results, 1):
        url = result.get("url", "")
        title = result.get("title") or url
        snippet = result.get("snippet", "")
        fetched = fetched_pages.get(url, {})
        text = fetched.get("text") if fetched.get("ok") else ""
        if not text:
            text = snippet
        text = (text or "").strip()
        if len(text) > max_source_chars:
            text = text[:max_source_chars].rstrip() + "\n... (source excerpt truncated)"
        sources.append({"index": idx, "title": title, "url": url, "snippet": snippet})
        context_parts.append(
            f"[{idx}] {title}\nURL: {url}\nSnippet: {snippet}\nContent excerpt:\n{text}"
        )

    if not context_parts:
        return "", sources

    context = (
        "You have fresh web search context below. Answer the user's question using these sources. "
        "Cite source numbers like [1] or [2] for factual claims. If the sources are insufficient, say so.\n\n"
        + "\n\n---\n\n".join(context_parts)
    )
    return context, sources


@functools.lru_cache(maxsize=1)
def get_local_interface_addresses() -> frozenset[str]:
    addresses = {config.LLAMA_HOST, "::1"}
    hostnames = {socket.gethostname(), socket.getfqdn()}
    for name in hostnames:
        try:
            for info in socket.getaddrinfo(name, None):
                addresses.add(info[4][0])
        except OSError:
            pass
    return frozenset(addresses)


def get_local_proxy_host(host: Any) -> tuple[str, str]:
    value = str(host or config.LLAMA_HOST).strip() or config.LLAMA_HOST
    if value.lower() == "localhost" or value in {"0.0.0.0", "::", "*"}:
        return config.LLAMA_HOST, ""
    try:
        infos = socket.getaddrinfo(value, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        return "", f"Invalid llama-server metrics host: {exc}"
    local_addresses = get_local_interface_addresses()
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_loopback or info[4][0] in local_addresses:
            return value, ""
    return "", "Blocked: metrics proxy can only target this machine."


def get_local_chat_api_url(body: Mapping[str, Any]) -> str:
    host = str(body.get("host") or config.LLAMA_HOST).strip() or config.LLAMA_HOST
    try:
        port = int(body.get("port") or config.LLAMA_PORT)
    except (TypeError, ValueError):
        raise ValueError("Invalid llama-server chat port.")
    if port < 1 or port > 65535:
        raise ValueError("Invalid llama-server chat port.")
    chat_host, host_error = get_local_proxy_host(host)
    if not chat_host:
        raise ValueError(host_error)
    return f"http://{chat_host}:{port}/v1/chat/completions"
