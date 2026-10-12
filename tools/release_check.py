"""Audit Git-eligible files without staging, printing secrets, or using a network.

Optionally export exactly that file set to a new directory for clean-room tests.
This is a publication guard, not a comprehensive secret scanner or history audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
DENIED_PARTS = {".git", ".idea", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
PATTERNS = (
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    rb"\bgithub_pat_[A-Za-z0-9_]{30,}\b",
    rb"\bAKIA[A-Z0-9]{16}\b",
    rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b",
    rb'''(?i)["']?(?:accountkey|lta_datamall_api_key|lta_account_key)["']?\s*[:=]\s*["']([A-Za-z0-9+/=_-]{20,})["']''',
)


def git_files(root):
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
    )
    return sorted({os.fsdecode(p) for p in raw.split(b"\0") if p})


def inspect_file(root, relative, secrets=()):
    path = root / relative
    parts = Path(relative).parts
    reasons = []
    if (any(p in DENIED_PARTS for p in parts)
            or relative.startswith(("data/recorded/", "tmp/", "output/", ".playwright-cli/"))
            or path.name == ".env" or path.name.startswith(".env.")
            or path.suffix.lower() in {".key", ".pem", ".log", ".pdf"}):
        reasons.append("private/local file included")
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        return ["symlink or path outside repository"], None
    if not path.is_file():
        return ["missing file"], None
    size = path.stat().st_size
    if size > MAX_BYTES:
        return reasons + ["file exceeds 5 MiB publication budget"], None
    data = path.read_bytes()
    for pattern in PATTERNS:
        if re.search(pattern, data):
            reasons.append("credential-like content; review locally")
            break
    if any(secret and secret in data for secret in secrets):
        reasons.append("contains an active environment credential")
    return reasons, {"path": relative, "bytes": size, "sha256": hashlib.sha256(data).hexdigest()}


def audit(root=ROOT):
    secrets = [value.encode() for name, value in os.environ.items()
               if value and name in {"LTA_DATAMALL_API_KEY", "LTA_ACCOUNT_KEY", "GH_TOKEN", "GITHUB_TOKEN"}]
    issues, manifest = [], []
    for relative in git_files(root):
        reasons, record = inspect_file(root, relative, secrets)
        issues.extend({"path": relative, "reason": r} for r in reasons)
        if record:
            manifest.append(record)
    return issues, manifest


def export(root, destination, manifest):
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Export requires a new directory; no existing files will be overwritten")
    for record in manifest:
        source = root / record["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Source changed after audit; rerun the audit")
    destination.mkdir(parents=True)
    for record in manifest:
        target = destination / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / record["path"], target)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, help="New clean-room directory, usually under tmp/")
    args = parser.parse_args()
    issues, manifest = audit()
    summary = {"files": len(manifest), "bytes": sum(x["bytes"] for x in manifest),
               "issues": issues, "scope": "Git-eligible working files, not Git history"}
    print(json.dumps(summary, indent=2))
    if issues:
        raise SystemExit(1)
    if args.export:
        destination = export(ROOT, args.export, manifest)
        manifest_path = destination.with_name(destination.name + ".manifest.json")
        # The manifest lives outside the copy, so the copy contains only publishable files.
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        print(f"Exported {len(manifest)} files to {destination}")


if __name__ == "__main__":
    main()
