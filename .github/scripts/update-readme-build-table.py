#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


REPO = os.environ.get("GITHUB_REPOSITORY", "hellomrli/my-ImmortalWrt")
TOKEN = os.environ.get("GITHUB_TOKEN")
README = Path("README.md")
START = "<!-- BUILD_TABLE_START -->"
END = "<!-- BUILD_TABLE_END -->"

# The firmware target list lives in .github/targets.json; keep the table in
# step with the branches the workflows actually build.
TARGETS = [
    {
        "label": target["label"],
        "source": target["source"],
        "branch": target["branch"],
        "tag_prefix": f"{target['source']}-{target['branch']}-",
    }
    for target in json.loads(
        (Path(__file__).resolve().parent.parent / "targets.json").read_text(encoding="utf-8")
    )["targets"]
]


def api(path):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "my-immortalwrt-readme-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    try:
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API failed: {url}: {exc.code} {detail}") from exc


def latest_releases():
    releases = api("/releases?per_page=100")
    result = {}
    for target in TARGETS:
        result[target["tag_prefix"]] = next(
            (release for release in releases if release["tag_name"].startswith(target["tag_prefix"])),
            None,
        )
    return result


def format_time(value):
    if not value:
        return "-"
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M CST")


def build_table():
    releases = latest_releases()

    lines = [
        "| 构建目标 | 构建状态 | 最新版本 | 发布时间 | Release | 推荐下载 |",
        "|----------|----------|----------|----------|---------|----------|",
    ]

    for target in TARGETS:
        release = releases[target["tag_prefix"]]
        # Deliberately derived from released state only.  Reporting a live
        # "构建中" made this table flip several times per build cycle, and each
        # flip was a committed README change -- most of this repository's
        # history was build-table churn.
        status = "已发布" if release else "暂无 Release"

        if release:
            tag = release["tag_name"]
            version = f"`{tag}`"
            published = format_time(release.get("published_at") or release.get("created_at"))
            link = f"[下载]({release['html_url']})"
        else:
            version = "-"
            published = "-"
            link = "-"

        lines.append(
            f"| {target['label']} | {status} | {version} | {published} | {link} | `squashfs-combined-efi.img.gz` |"
        )

    lines.append("")
    lines.append("> 此表由 GitHub Actions 自动更新；新 Release 发布后会同步最新版本和链接。")
    return "\n".join(lines)


def main():
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        print(f"Missing markers {START} / {END} in README.md", file=sys.stderr)
        return 1

    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)
    updated = f"{before}{START}\n{build_table()}\n{END}{after}"

    if updated != readme:
        README.write_text(updated, encoding="utf-8")
        print("README build table updated.")
    else:
        print("README build table is already up to date.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
