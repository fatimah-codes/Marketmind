"""
MarketMind AI - Submission Packaging Script
Assembles the complete compliant submission archive: <RollNo>_MarketMind.zip.
Enforces Appendix C rules:
- Excludes .env, secrets, __pycache__, and git directories.
- Includes .env.example, full source code, docs, schemas, corpus, tests, and eval results.
"""

import os
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build"
}

EXCLUDE_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".env",
    ".key",
    ".DS_Store"
}


def package_project(roll_no: str = "AAI-412-STUDENT"):
    archive_name = f"{roll_no}_MarketMind.zip"
    zip_path = PROJECT_ROOT / archive_name

    print(f"\n[PACKAGING] Creating clean submission archive: {archive_name}")
    file_count = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(PROJECT_ROOT)

                # Skip self zip, real .env, pyc files
                if file == archive_name or file.endswith(".zip"):
                    continue
                if file == ".env" or any(file.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                if any(part in EXCLUDE_DIRS for part in rel_path.parts):
                    continue

                zip_file.write(file_path, arcname=str(rel_path))
                file_count += 1

    size_kb = zip_path.stat().st_size / 1024.0
    print(f"[SUCCESS] Packaged {file_count} files into '{archive_name}' ({size_kb:.1f} KB).")
    print(f"Archive Location: {zip_path}\n")
    return zip_path


if __name__ == "__main__":
    roll = sys.argv[1] if len(sys.argv) > 1 else "AAI-412-05_MarketMind"
    package_project(roll)
