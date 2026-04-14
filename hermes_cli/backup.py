"""
hermes backup / hermes restore

Creates and restores portable archives of the Hermes configuration.

What's included by default:
  config.yaml, .env (with warnings), SOUL.md, MEMORY.md, USER.md,
  skills/, cron.yaml, gateway.yaml, chronos.db, state.db (optional)

What's excluded by default:
  cache/, optional-skills/, home/ (tool configs), *.pyc, __pycache__

Usage:
    hermes backup                          # backup to ~/.hermes/backups/hermes_<date>.tar.gz
    hermes backup --output ~/my-backup.tar.gz
    hermes backup --include-sessions       # include state.db (can be large)
    hermes backup --no-secrets             # skip .env file

    hermes restore ~/my-backup.tar.gz
    hermes restore ~/my-backup.tar.gz --dry-run
    hermes restore ~/my-backup.tar.gz --merge    # merge instead of overwrite
"""

import json
import os
import sys
import tarfile
import time
from pathlib import Path
from typing import List, Optional, Set

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from hermes_cli.colors import Colors, color
from hermes_constants import get_hermes_home, display_hermes_home


# ─── Files/dirs always included ──────────────────────────────────────────────
_ALWAYS_INCLUDE = [
    "config.yaml",
    "SOUL.md",
    "MEMORY.md",
    "USER.md",
    "HERMES.md",
    "cron.yaml",
    "gateway.yaml",
    "auth.json",
    "active_profile",
]

_ALWAYS_INCLUDE_DIRS = [
    "skills",
    "memories",
    "profiles",
]

# ─── Files conditionally included ────────────────────────────────────────────
_SECRETS_FILE = ".env"
_SESSIONS_DB = "state.db"
_CHRONOS_DB = "chronos.db"

# ─── Exclusion patterns ───────────────────────────────────────────────────────
_EXCLUDE_DIRS = {"cache", "optional-skills", "home", "__pycache__", ".git", "node_modules"}
_EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".log"}


def _collect_backup_files(
    hermes_home: Path,
    include_sessions: bool = False,
    include_secrets: bool = True,
) -> List[Path]:
    """Return list of files to include in the backup archive."""
    files: List[Path] = []

    # Single files
    for name in _ALWAYS_INCLUDE:
        p = hermes_home / name
        if p.exists():
            files.append(p)

    # Conditional files
    if include_secrets:
        p = hermes_home / _SECRETS_FILE
        if p.exists():
            files.append(p)

    if include_sessions:
        p = hermes_home / _SESSIONS_DB
        if p.exists():
            files.append(p)

    p = hermes_home / _CHRONOS_DB
    if p.exists():
        files.append(p)

    # Directories (recursive, with exclusions)
    for dir_name in _ALWAYS_INCLUDE_DIRS:
        d = hermes_home / dir_name
        if not d.exists():
            continue
        for root, dirs, filenames in os.walk(d):
            root_path = Path(root)
            # Prune excluded dirs in-place
            dirs[:] = [
                dd for dd in dirs
                if dd not in _EXCLUDE_DIRS and not dd.startswith(".")
            ]
            for fname in filenames:
                if Path(fname).suffix in _EXCLUDE_EXTENSIONS:
                    continue
                files.append(root_path / fname)

    return files


def backup_command(args) -> None:
    """Run hermes backup."""
    hermes_home = get_hermes_home()
    include_sessions = getattr(args, "include_sessions", False)
    no_secrets = getattr(args, "no_secrets", False)
    output_path = getattr(args, "output", None)

    include_secrets = not no_secrets

    print(color("⏫ Hermes Backup", Colors.CYAN))
    print(color(f"   Source: {display_hermes_home()}", Colors.DIM))

    if not output_path:
        backup_dir = hermes_home / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = str(backup_dir / f"hermes_{timestamp}.tar.gz")

    output_path = Path(output_path).expanduser().resolve()

    files = _collect_backup_files(hermes_home, include_sessions, include_secrets)

    if not files:
        print(color("  Nothing to back up — Hermes home appears empty.", Colors.DIM))
        return

    if no_secrets:
        print(color("  Note: .env (secrets) excluded from this backup.", Colors.DIM))
    elif include_secrets:
        env_path = hermes_home / ".env"
        if env_path.exists():
            print(color("  Warning: .env (API keys) will be included. Keep the archive secure.", Colors.DIM))

    # Write tarball
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(output_path), "w:gz") as tar:
        for f in files:
            arcname = os.path.relpath(str(f), str(hermes_home))
            tar.add(str(f), arcname=arcname)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(color(f"  Backed up {len(files)} files → {output_path}", Colors.CYAN))
    print(color(f"  Archive size: {size_mb:.2f} MB", Colors.DIM))
    if include_sessions:
        print(color("  Sessions (state.db) included.", Colors.DIM))
    print()

    # Write manifest
    manifest_path = output_path.with_suffix("").with_suffix(".manifest.json")
    manifest = {
        "created_at": time.time(),
        "hermes_home": str(hermes_home),
        "file_count": len(files),
        "include_sessions": include_sessions,
        "include_secrets": include_secrets,
        "files": [os.path.relpath(str(f), str(hermes_home)) for f in files],
    }
    try:
        manifest_path.write_text(json.dumps(manifest, indent=2))
    except Exception:
        pass  # manifest is best-effort


def restore_command(args) -> None:
    """Run hermes restore."""
    archive_path = Path(getattr(args, "archive", "")).expanduser().resolve()
    dry_run = getattr(args, "dry_run", False)
    merge = getattr(args, "merge", False)

    print(color("⏬ Hermes Restore", Colors.CYAN))

    if not archive_path.exists():
        print(color(f"  Error: archive not found: {archive_path}", Colors.DIM))
        sys.exit(1)

    hermes_home = get_hermes_home()
    print(color(f"   Target: {display_hermes_home()}", Colors.DIM))

    if dry_run:
        print(color("  [DRY RUN] No files will be written.", Colors.DIM))

    # List archive contents
    try:
        with tarfile.open(str(archive_path), "r:gz") as tar:
            members = tar.getmembers()
    except Exception as e:
        print(color(f"  Error reading archive: {e}", Colors.DIM))
        sys.exit(1)

    print(color(f"  Archive: {archive_path.name} ({len(members)} files)", Colors.DIM))

    # Check for conflicts
    conflicts: List[str] = []
    for m in members:
        target = hermes_home / m.name
        if target.exists() and not merge:
            conflicts.append(m.name)

    if conflicts and not dry_run:
        print(color(f"\n  {len(conflicts)} existing files will be overwritten.", Colors.DIM))
        try:
            reply = input("  Continue? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            reply = "n"
        if reply != "y":
            print(color("  Restore cancelled.", Colors.DIM))
            return

    if not dry_run:
        hermes_home.mkdir(parents=True, exist_ok=True)
        with tarfile.open(str(archive_path), "r:gz") as tar:
            tar.extractall(str(hermes_home))
        print(color(f"  Restored {len(members)} files to {display_hermes_home()}", Colors.CYAN))
        print(color("  Restart Hermes for changes to take effect.", Colors.DIM))
    else:
        for m in members:
            status = "[OVERWRITE]" if (hermes_home / m.name).exists() else "[NEW]"
            print(f"  {status} {m.name}")
    print()
