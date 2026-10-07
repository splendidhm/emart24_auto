"""Opt-in real Excel integration; only writes below runtime/validation/<uuid>."""
import json
import shutil
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from emart24.core import StopRun, Retryable, file_hash, fingerprint, load_config
from emart24.importer import import_file
from emart24.workbooks import excel, read_source, read_xlsx
from emart24.windows import protect_target


def snapshot(path, last):
    wb = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        result = {}
        for ws in wb:
            rows = []
            for row in ws.iter_rows():
                for c in row:
                    if c.value is not None and not (ws.title == "DB" and c.row > last and c.column <= 20):
                        rows.append([c.coordinate, c.value, c.number_format])
            result[ws.title] = fingerprint(rows)
        return result
    finally:
        wb.close()


def run(source):
    cfg = load_config("config.json")
    production = Path(cfg["target"])
    original_hash = file_hash(production)
    root = Path("runtime/validation") / uuid.uuid4().hex
    root.mkdir(parents=True)
    target = root / "target.xlsx"
    shutil.copy2(production, target)
    cfg["target"] = str(target.resolve())
    cfg["runtime"] = str((root / "state").resolve())
    _, rows = read_source(source, cfg["source_headers"])
    # Two distinguishable rows exercise text IDs, formula-looking strings and numbers.
    sample = [list(rows[0]), list(rows[-1])]
    sample[0][0] = "00001"
    sample[0][3] = "=must remain text"
    sample[1][3] = "integration-" + uuid.uuid4().hex
    sample[1][0] = "'literal apostrophe"
    sample_source = root / "source.xlsx"
    with excel() as app:
        wb = app.Workbooks.Add()
        try:
            ws = wb.Worksheets(1)
            ws.Name = "붙여넣기"
            ws.Range("A1:O1").Value2 = (tuple(cfg["source_headers"]),)
            ws.Range("A2:O3").Value2 = tuple(tuple("'"+v if isinstance(v,str) else v for v in row) for row in sample)
            wb.SaveAs(str(sample_source.resolve()), FileFormat=51)
        finally:
            wb.Close(False)
    assert read_source(sample_source,cfg["source_headers"])[1] == sample
    existing = read_xlsx(target,"DB")[2]
    before_snapshot = snapshot(target,len(existing)+1)
    before_hash = file_hash(target)
    dry = import_file(cfg,sample_source,"2026-10-07",dry_run=True)
    assert dry["status"] == "would_append" and file_hash(target)==before_hash
    assert not (Path(cfg["runtime"])/"history.sqlite3").exists()
    # A real file lock prevents writing; original must stay byte-identical.
    import win32con, win32file
    h = win32file.CreateFile(str(target.resolve()),win32con.GENERIC_READ,0,None,win32con.OPEN_EXISTING,0,None)
    try:
        try:
            import_file(cfg,sample_source,"2026-10-07")
            raise AssertionError("lock was ignored")
        except Retryable:
            pass
    finally:
        h.Close()
    assert file_hash(target)==before_hash
    # Force interruption before replacing the target; it must remain unchanged.
    with patch("emart24.importer.replace_file",side_effect=PermissionError("test")):
        try:
            import_file(cfg,sample_source,"2026-10-07")
            raise AssertionError("replace failure ignored")
        except Retryable:
            pass
    assert file_hash(target)==before_hash
    result = import_file(cfg,sample_source,"2026-10-07")
    assert result["status"] == "committed"
    assert file_hash(Path(result["backup"])) == before_hash
    assert snapshot(target,len(existing)+1)==before_snapshot, "Existing sheet values/formulas/formats changed"
    after = file_hash(target)
    assert import_file(cfg,sample_source,"2026-10-07")["status"]=="already_present"
    assert file_hash(target)==after
    # Existing real sample must also be recognized without appending.
    assert import_file(cfg,source,"2026-10-06",dry_run=True)["status"]=="already_present"
    assert file_hash(production)==original_hash
    report = {"passed":True,"test_directory":str(root.resolve()),"added_rows":len(sample),
              "preserved_sheets":len(before_snapshot),"production_unchanged":True,
              "checks":["dry_run","text_identifiers","formula_like_text","file_lock","replace_failure_recovery","append","P:T_formulas","existing_sheet_preservation","backup","rerun_duplicate","manual_existing_batch"]}
    (root/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run(Path(sys.argv[1]))
