"""Verify the delivery hashes recorded in SOURCE.json without network access."""

import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "SOURCE.json").read_text(encoding="utf-8"))
    hashes = manifest["delivery_sha256"]
    mismatches = []
    for name, expected in hashes.items():
        path = root / name
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            mismatches.append(name)
    if mismatches:
        raise SystemExit("Changed or missing files: " + ", ".join(mismatches))
    print(f"Verified {len(hashes)} delivery files")


if __name__ == "__main__":
    main()
