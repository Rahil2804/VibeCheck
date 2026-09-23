from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "OpenAI API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "Mapbox token": re.compile(r"\bpk\.eyJ[A-Za-z0-9._-]{20,}"),
}


def main() -> None:
    files = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    findings: list[str] = []
    for relative in files:
        path = Path(relative)
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{relative}: possible {label}")
    if findings:
        print("Secret scan failed:\n" + "\n".join(findings))
        raise SystemExit(1)
    print(f"Secret scan passed ({len(files)} repository files checked).")


if __name__ == "__main__":
    main()
