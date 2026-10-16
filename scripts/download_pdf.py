"""Download the employee handbook PDF into data/.

Reads PDF_URL from .env (repo root) if present, else uses the default URL.
Skips download when data/employee_handbook.pdf already exists unless --force.
Works offline: existing file is reused, missing file prints a clear message.
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = (
    "https://raw.githubusercontent.com/Azure-Samples/"
    "azure-search-openai-demo/main/data/employee_handbook.pdf"
)
SECONDARY_URL = (
    "https://raw.githubusercontent.com/Azure-Samples/"
    "azure-search-openai-demo/main/data/Northwind_Standard_Benefits_Details.pdf"
)

ROOT = Path(__file__).resolve().parents[1]  # repo root (scripts/ -> root)
DEST = ROOT / "data" / "employee_handbook.pdf"
DEST_SECONDARY = ROOT / "data" / "Northwind_Standard_Benefits_Details.pdf"


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (no dependency, no interpolation)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def pdf_url() -> str:
    if os.environ.get("PDF_URL"):
        return os.environ["PDF_URL"]
    return load_env_file(ROOT / ".env").get("PDF_URL", DEFAULT_URL)


def secondary_url() -> str:
    if os.environ.get("SECONDARY_PDF_URL"):
        return os.environ["SECONDARY_PDF_URL"]
    return load_env_file(ROOT / ".env").get("SECONDARY_PDF_URL", SECONDARY_URL)


def download(url: str, dest: Path = DEST, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0 and not force:
        print(f"exists: {dest} ({dest.stat().st_size} bytes), skipping (use --force to re-download)")
        return dest
    print(f"downloading: {url}\n  -> {dest}")
    urllib.request.urlretrieve(url, dest)  # noqa: S310 (trusted handbook URL)
    print(f"saved: {dest} ({dest.stat().st_size} bytes)")
    return dest


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    force = "--force" in args
    ok = True
    for url, dest in ((pdf_url(), DEST), (secondary_url(), DEST_SECONDARY)):
        if dest.is_file() and dest.stat().st_size > 0 and not force:
            print(f"exists: {dest}, skipping")
            continue
        try:
            download(url, dest, force=force)
        except Exception as exc:  # offline / no network: keep going with a message
            if dest.is_file() and dest.stat().st_size > 0:
                print(f"warning: download failed ({exc}); reusing existing {dest}")
                continue
            if dest == DEST_SECONDARY:
                print(f"warning: secondary benefits PDF unavailable ({exc}); continuing with handbook only")
                continue
            print(f"error: could not download handbook ({exc}); "
                  f"place the PDF at {dest} manually and re-run ingest")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
