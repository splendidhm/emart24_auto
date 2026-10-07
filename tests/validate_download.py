"""Validate an unchanged downloaded batch against a disposable production copy."""
import argparse
import json
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path

from emart24.core import file_hash, load_config
from emart24.importer import import_file
from emart24.windows import protect_target
from emart24.workbooks import read_xlsx
from tests.integration_excel import snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    cfg = load_config()
    production = Path(cfg["target"])
    root = Path(cfg["runtime"]) / "validation" / (str(args.date) + "-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    target = root / production.name
    source = root / ("download-" + args.source.name)
    with protect_target(production):
        original_hash = file_hash(production)
        shutil.copy2(production, target)
        if file_hash(target) != original_hash:
            raise RuntimeError("Production copy changed during copy")
    shutil.copy2(args.source, source)
    if file_hash(source) != file_hash(args.source):
        raise RuntimeError("Downloaded copy mismatch")
    cfg["target"] = str(target)
    cfg["runtime"] = str(root / "state")
    existing = read_xlsx(target, cfg["sheet"])[2]
    before = snapshot(target, len(existing) + 1)
    first = import_file(cfg, source, args.date)
    after_hash = file_hash(target)
    again = import_file(cfg, source, args.date)
    assert again["status"] == "already_present"
    assert file_hash(target) == after_hash
    assert snapshot(target, len(existing) + 1) == before
    assert file_hash(production) == original_hash
    report = {"passed": True, "date": str(args.date), "first_result": first,
              "repeat_result": again["status"], "production_unchanged": True,
              "preserved_sheets": len(before), "test_directory": str(root),
              "append_exercised": first["status"] == "committed"}
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
