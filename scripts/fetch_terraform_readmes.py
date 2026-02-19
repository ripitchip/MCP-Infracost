#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://api.github.com"
USER_AGENT = "readme-extractor/1.0"
FOOTER_TITLES = {
    "authors",
    "author",
    "license",
    "maintainers",
    "maintainer",
    "contributing",
    "contribution",
    "support",
    "changelog",
    "additional information",
    "security",
}


def api_request(url: str, token: Optional[str] = None) -> Tuple[dict, Dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            header_map = {k.lower(): v for k, v in response.headers.items()}
            return payload, header_map
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        rate_remaining = error.headers.get("X-RateLimit-Remaining")
        rate_reset = error.headers.get("X-RateLimit-Reset")
        if error.code == 403 and rate_remaining == "0":
            reset_info = ""
            if rate_reset and rate_reset.isdigit():
                reset_info = (
                    f" (resets in ~{max(0, int(rate_reset) - int(time.time()))}s)"
                )
            raise RuntimeError(
                "GitHub API rate limit reached. Set GITHUB_TOKEN for higher limits"
                f"{reset_info}."
            ) from error
        raise RuntimeError(f"HTTP {error.code} for {url}: {body}") from error
    except URLError as error:
        raise RuntimeError(f"Network error for {url}: {error}") from error


def list_org_repositories(org: str, token: Optional[str]) -> List[dict]:
    page = 1
    repos: List[dict] = []

    while True:
        query = urlencode({"per_page": 100, "page": page, "type": "public"})
        url = f"{API_BASE}/orgs/{org}/repos?{query}"
        payload, _ = api_request(url, token=token)
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected response for repo list: {payload}")
        if not payload:
            break
        repos.extend(payload)
        page += 1

    return repos


def fetch_readme(org: str, repo: str, token: Optional[str]) -> Tuple[str, str]:
    url = f"{API_BASE}/repos/{org}/{repo}/readme"
    payload, _ = api_request(url, token=token)

    if not isinstance(payload, dict) or "content" not in payload:
        raise RuntimeError(f"No README found for {org}/{repo}")

    encoding = payload.get("encoding")
    if encoding != "base64":
        raise RuntimeError(f"Unsupported README encoding for {org}/{repo}: {encoding}")

    content = payload["content"].replace("\n", "")
    decoded = base64.b64decode(content).decode("utf-8", errors="replace")
    path = payload.get("path", "README.md")
    return decoded, path


def is_badge_or_banner_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("[![") or stripped.startswith("!["):
        return True
    if "shields.io" in stripped:
        return True
    if "badge" in stripped.lower() and (
        "http://" in stripped or "https://" in stripped
    ):
        return True
    return False


def normalize_heading_title(line: str) -> str:
    title = re.sub(r"^#{1,6}\s*", "", line).strip().lower()
    title = re.sub(r"\s+", " ", title)
    return title


def find_first_title(lines: List[str]) -> Optional[int]:
    for index, line in enumerate(lines):
        if line.strip().startswith("# "):
            return index
    return None


def find_content_start(lines: List[str], title_index: Optional[int]) -> int:
    usage_heading = re.compile(r"^##\s+usage\b", re.IGNORECASE)
    for i, line in enumerate(lines):
        if usage_heading.match(line.strip()):
            return i + 1

    for i, line in enumerate(lines):
        if line.strip().startswith("### "):
            return i

    if title_index is not None:
        return title_index + 1

    return 0


def find_content_end(lines: List[str], start: int) -> int:
    heading_pattern = re.compile(r"^##+\s+")
    for i in range(start, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        if heading_pattern.match(line):
            title = normalize_heading_title(line)
            if title in FOOTER_TITLES:
                return i
    return len(lines)


def compact_blank_lines(lines: List[str]) -> List[str]:
    compacted: List[str] = []
    blank_run = 0
    for line in lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                compacted.append("")
        else:
            blank_run = 0
            compacted.append(line.rstrip())

    while compacted and compacted[0] == "":
        compacted.pop(0)
    while compacted and compacted[-1] == "":
        compacted.pop()

    return compacted


def clean_readme(markdown_text: str) -> str:
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    title_index = find_first_title(lines)
    title_block: List[str] = []
    if title_index is not None:
        title_block.append(lines[title_index].rstrip())

        # Keep the first non-empty, non-heading paragraph line under title.
        for i in range(title_index + 1, min(title_index + 12, len(lines))):
            stripped = lines[i].strip()
            if not stripped:
                continue
            if stripped.startswith("#") or is_badge_or_banner_line(stripped):
                continue
            title_block.extend(["", lines[i].rstrip()])
            break

    start = find_content_start(lines, title_index)
    end = find_content_end(lines, start)
    body_lines = lines[start:end]

    filtered_body: List[str] = []
    for line in body_lines:
        stripped = line.strip()
        if is_badge_or_banner_line(stripped):
            continue
        if re.match(r"^##\s+usage\b", stripped, flags=re.IGNORECASE):
            continue
        filtered_body.append(line.rstrip())

    output_lines = compact_blank_lines(
        title_block + [""] + filtered_body if title_block else filtered_body
    )
    return "\n".join(output_lines) + "\n"


def next_extract_directory(downloads_path: Path) -> Path:
    downloads_path.mkdir(parents=True, exist_ok=True)
    existing_numbers: List[int] = []
    for child in downloads_path.iterdir():
        if child.is_dir():
            match = re.fullmatch(r"extract(\d+)", child.name)
            if match:
                existing_numbers.append(int(match.group(1)))

    next_num = max(existing_numbers, default=0) + 1
    out_dir = downloads_path / f"extract{next_num}"
    out_dir.mkdir(parents=True, exist_ok=False)
    return out_dir


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_env_file(env_path: Path) -> None:
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue
        if value.startswith(('"', "'")) and value.endswith(('"', "'")):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def run(org: str, root: Path, include_archived: bool, token: Optional[str]) -> Path:
    downloads_dir = root / "downloads"
    output_root = next_extract_directory(downloads_dir)

    repos = list_org_repositories(org, token=token)

    summary = {
        "organization": org,
        "output": str(output_root),
        "repository_count": len(repos),
        "processed": [],
        "skipped": [],
        "generated_at": int(time.time()),
    }

    for repo_info in repos:
        name = repo_info.get("name")
        if not name:
            continue

        archived = bool(repo_info.get("archived", False))
        if archived and not include_archived:
            summary["skipped"].append({"repo": name, "reason": "archived"})
            continue

        try:
            original, readme_path = fetch_readme(org, name, token=token)
            cleaned = clean_readme(original)
        except Exception as error:
            summary["skipped"].append({"repo": name, "reason": str(error)})
            continue

        repo_dir = output_root / name
        write_text(repo_dir / "README.original.md", original)
        write_text(repo_dir / "README.cleaned.md", cleaned)

        summary["processed"].append(
            {
                "repo": name,
                "readme_path": readme_path,
                "original_file": str(
                    (repo_dir / "README.original.md").relative_to(root)
                ),
                "cleaned_file": str((repo_dir / "README.cleaned.md").relative_to(root)),
            }
        )

    write_text(output_root / "summary.json", json.dumps(summary, indent=2))

    index_lines = [
        f"# README extraction for `{org}`",
        "",
        f"- Total repos discovered: {summary['repository_count']}",
        f"- Processed: {len(summary['processed'])}",
        f"- Skipped: {len(summary['skipped'])}",
        "",
        "## Processed repositories",
        "",
    ]

    for item in summary["processed"]:
        index_lines.append(f"- `{item['repo']}` → `{item['cleaned_file']}`")

    if summary["skipped"]:
        index_lines.extend(["", "## Skipped repositories", ""])
        for item in summary["skipped"]:
            index_lines.append(f"- `{item['repo']}`: {item['reason']}")

    write_text(output_root / "README.md", "\n".join(index_lines).rstrip() + "\n")

    return output_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crawl all repositories from a GitHub organization, download READMEs, "
            "and produce cleaned example-focused extracts in downloads/extractN/."
        )
    )
    parser.add_argument(
        "--org", default="terraform-aws-modules", help="GitHub organization"
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Workspace root containing ./downloads (default: repository root)",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived repositories",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    load_env_file(root / ".env")
    token = os.getenv("GITHUB_TOKEN")
    if token:
        print("Using GITHUB_TOKEN for authenticated API requests.")

    try:
        output = run(
            org=args.org,
            root=root,
            include_archived=args.include_archived,
            token=token,
        )
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Done. Output directory: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
