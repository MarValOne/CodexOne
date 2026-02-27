one
#!/usr/bin/env python3
"""Production-ready web title scraper.

This script fetches an HTML page, extracts elements by CSS selector (default: h2),
and outputs cleaned text values. It includes:
- Robust HTTP handling with retries and timeouts
- Input validation
- Structured logging
- JSON or text output formats
- Optional output file writing

Environment setup (recommended):
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

Example:
    python one.py --url https://example.com --selector h1 --format json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT = 10
DEFAULT_SELECTOR = "h2"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class ScrapeResult:
    """Holds metadata and extracted texts from a scrape operation."""

    url: str
    selector: str
    items: list[str]


class ScraperError(RuntimeError):
    """Raised for recoverable scraper failures."""


def configure_logging(verbose: bool) -> None:
    """Configure root logging with either INFO or DEBUG verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_session(user_agent: str, retries: int, backoff_seconds: float) -> requests.Session:
    """Build a requests session with retry strategy and hardened defaults."""
    if retries < 0:
        raise ValueError("retries must be >= 0")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must be >= 0")

    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=backoff_seconds,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"})
    return session


def fetch_html(session: requests.Session, url: str, timeout: int) -> str:
    """Fetch and return raw HTML content, raising ScraperError on failure."""
    if timeout <= 0:
        raise ValueError("timeout must be > 0")

    try:
        logging.debug("Requesting URL: %s", url)
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ScraperError(f"HTTP request failed for {url}: {exc}") from exc

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        logging.warning("Response content-type is '%s', expected HTML", content_type)

    return response.text


def parse_elements(html: str, selector: str) -> list[str]:
    """Extract cleaned text content for all elements matching selector."""
    if not selector.strip():
        raise ValueError("selector cannot be empty")

    soup = BeautifulSoup(html, "html.parser")
    elements = soup.select(selector)
    cleaned = [el.get_text(" ", strip=True) for el in elements]
    return [text for text in cleaned if text]


def scrape(url: str, selector: str, timeout: int, retries: int, backoff_seconds: float, user_agent: str) -> ScrapeResult:
    """Perform full scrape pipeline and return structured result."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")

    session = build_session(user_agent=user_agent, retries=retries, backoff_seconds=backoff_seconds)
    html = fetch_html(session=session, url=url, timeout=timeout)
    items = parse_elements(html=html, selector=selector)
    logging.info("Found %d matching element(s) using selector '%s'", len(items), selector)
    return ScrapeResult(url=url, selector=selector, items=items)


def render_output(result: ScrapeResult, output_format: str) -> str:
    """Render scrape result as plain text or JSON string."""
    if output_format == "text":
        return "\n".join(result.items)

    payload = {
        "url": result.url,
        "selector": result.selector,
        "count": len(result.items),
        "items": result.items,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_output(content: str, output_path: Path | None) -> None:
    """Write output to stdout or a file path."""
    if output_path is None:
        print(content)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content + "\n", encoding="utf-8")
    logging.info("Output written to %s", output_path)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Production-grade web element text scraper",
        epilog="Tip: create a virtual environment and install requirements.txt before running.",
    )
    parser.add_argument("--url", required=True, help="Target URL (must start with http:// or https://)")
    parser.add_argument("--selector", default=DEFAULT_SELECTOR, help="CSS selector to extract (default: h2)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    parser.add_argument("--retries", type=int, default=3, help="Retry attempts for transient HTTP errors")
    parser.add_argument("--backoff", type=float, default=0.5, help="Exponential backoff factor between retries")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP User-Agent header")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    configure_logging(args.verbose)

    try:
        result = scrape(
            url=args.url,
            selector=args.selector,
            timeout=args.timeout,
            retries=args.retries,
            backoff_seconds=args.backoff,
            user_agent=args.user_agent,
        )
        output = render_output(result=result, output_format=args.format)
        write_output(content=output, output_path=args.output)
        return 0
    except (ValueError, ScraperError) as exc:
        logging.error("%s", exc)
        return 2
    except Exception as exc:  # Defensive fallback for unexpected failures.
        logging.exception("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())