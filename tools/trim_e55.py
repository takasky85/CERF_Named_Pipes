#!/usr/bin/env python3
"""Trim a CERF checkout so that it offers only the Casio Cassiopeia E-55.

By default only the CE guest apps are skipped (all devices are kept); pass --e55-only to also trim the device list.
Run from the root of a gweslab/cerf checkout (submodules initialised).

What it does:
  * libCerfCore/db/boards: keeps only casio_cassiopeia_e55.json (+ index.json)
  * libCerfCore/db/board_families: keeps only casio_tomcat (the E-55's family) (+ index.json)
  * ce_apps/*/build.py: removed. The CE guest apps need a private CE toolchain that is not
    available to CI; the E-55 ROM boots without them (guest additions are simply missing).

What it deliberately does NOT do: delete the C++ sources of other boards. They register themselves
only when their board family is selected, so they are dead code in this build. Removing them blind
risks breaking the link; do that only with a local build to check against.
"""
import shutil
import sys
from pathlib import Path

KEEP_BOARD = "casio_cassiopeia_e55.json"
KEEP_FAMILY = "casio_tomcat"


def prune(directory: Path, keep: str) -> int:
    removed = 0
    for entry in sorted(directory.iterdir()):
        if entry.name in (keep, "index.json"):
            continue
        shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
        removed += 1
    return removed


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = Path(args[0] if args else ".").resolve()
    db = root / "libCerfCore" / "db"
    if not (db / "boards" / KEEP_BOARD).is_file():
        print("not a CERF checkout (missing {})".format(db / "boards" / KEEP_BOARD))
        return 1
    if "--e55-only" in sys.argv:
        print("boards removed:", prune(db / "boards", KEEP_BOARD))
        print("board families removed:", prune(db / "board_families", KEEP_FAMILY))
    for script in (root / "ce_apps").glob("*/build.py"):
        script.unlink()
        print("removed", script.relative_to(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
