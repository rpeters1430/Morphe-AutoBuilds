#!/usr/bin/env python3
"""Upload immutable artifacts, leaving existing release bytes untouched."""
import json
import subprocess
import sys
from pathlib import Path


def upload(paths: list[str]) -> None:
    result = subprocess.run(["gh", "release", "view", "latest", "--json", "assets"],
                            capture_output=True, text=True, check=True, timeout=120)
    existing = {asset["name"] for asset in json.loads(result.stdout)["assets"]}
    pending = [path for path in paths if Path(path).name not in existing]
    if pending:
        subprocess.run(["gh", "release", "upload", "latest", *pending], check=True, timeout=1200)
    else:
        print("Identical immutable assets are already published.")


if __name__ == "__main__":
    upload(sys.argv[1:])
