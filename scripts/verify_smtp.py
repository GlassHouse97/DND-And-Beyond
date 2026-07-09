"""Verify production SMTP credentials without touching app data."""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Copy .env.production.example and fill it in first.")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Check production SMTP login settings.")
    parser.add_argument("--env-file", default=".env.production")
    args = parser.parse_args()

    try:
        load_env_file(Path(args.env_file))
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    if not host or not username or not password:
        print("SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD are required.", file=sys.stderr)
        return 1

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(username, password)
    except smtplib.SMTPAuthenticationError:
        print("SMTP_AUTH_FAILED: use a Gmail App Password, not your normal Google password.", file=sys.stderr)
        return 1
    except (OSError, smtplib.SMTPException) as exc:
        print(f"SMTP_CHECK_FAILED: {exc}", file=sys.stderr)
        return 1

    print("SMTP_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
