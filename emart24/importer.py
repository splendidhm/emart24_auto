from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from .core import Retryable, StopRun, file_hash, fingerprint, overlap
from .ledger import Ledger
from .windows import protect_target, replace_file
from .workbooks import append_with_excel, read_source, read_xlsx, template_formulas, verify_append


def import_file(cfg, source, day, transfer=None, dry_run=False):
    target = Path(cfg["target"]).resolve()
    source = Path(source).resolve()
    if source == target:
        raise StopRun("원본과 대상 경로가 같습니다.")
    if not target.is_file():
        raise StopRun("대상 파일을 찾을 수 없습니다.")
    source_hash = file_hash(source)
    source_sheet, rows = read_source(source, cfg["source_headers"])
    if file_hash(source) != source_hash:
        raise StopRun("읽는 동안 원본 파일이 변경됐습니다.")
    digest = fingerprint(rows)
    runtime = Path(cfg["runtime"])
    ledger = Ledger(runtime / "history.sqlite3", readonly=dry_run)
    work = None
    try:
        with protect_target(target):
            if not dry_run:
                ledger.recover(target, cfg["sheet"])
            elif any(r["status"] == "prepared" for r in ledger.records(target)):
                raise StopRun("미완료 저장 이력이 있습니다. 일반 실행에서 복구 후 미리보기를 실행하세요.")
            before = file_hash(target)
            _, _, existing = read_xlsx(target, cfg["sheet"])
            previous = ledger.previous(target, str(day), str(transfer) if transfer else None, digest)
            duplicate = overlap(rows, existing)
            if previous and duplicate != "all":
                raise StopRun("처리 이력과 DB 데이터가 일치하지 않습니다. 복구가 필요합니다.")
            if duplicate == "partial":
                raise StopRun("원본 일부 행만 이미 DB에 있습니다. 중복·누락 검토가 필요합니다.")
            start = len(existing) + 2
            result = {"status": "already_present" if duplicate == "all" else "would_append" if dry_run else "committed",
                      "date": str(day), "source_sheet": source_sheet, "rows": len(rows), "start_row": None if duplicate == "all" else start,
                      "dry_run": dry_run, "source_hash": source_hash}
            fields = dict(id=uuid.uuid4().hex, target=str(target), day=str(day), transfer=str(transfer) if transfer else None,
                          source_hash=result["source_hash"], data_hash=digest, row_count=len(rows))
            if duplicate == "all":
                if not dry_run and not previous:
                    ledger.put(**fields, status="existing")
                return result
            formulas = template_formulas(target, cfg["sheet"], start - 1)
            if dry_run:
                return result
            backup_dir = runtime / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"{day}_{fields['id']}_{target.name}"
            shutil.copy2(target, backup)
            if file_hash(backup) != before:
                raise StopRun("백업 검증에 실패했습니다.")
            work = target.with_name(f".emart24-{fields['id']}.xlsx")
            shutil.copy2(target, work)
            append_with_excel(work, cfg["sheet"], rows, start)
            verify_append(work, cfg["sheet"], existing, rows, start, formulas)
            after = file_hash(work)
            ledger.put(**fields, status="prepared", start_row=start, before_hash=before, after_hash=after, backup=str(backup))
            if file_hash(target) != before or target.with_name("~$" + target.name).exists():
                raise Retryable("저장 직전 대상 파일이 변경되었거나 열렸습니다.")
            try:
                replace_file(work, target)
            except PermissionError as exc:
                raise Retryable("대상 파일 사용 중으로 교체하지 못했습니다.") from exc
            if file_hash(target) != after:
                raise StopRun("교체 후 파일 검증 실패: 복구 이력을 확인하세요.")
            ledger.status(fields["id"], "committed")
            result["backup"] = str(backup)
            return result
    finally:
        if work is not None and work.exists():
            work.unlink()
        ledger.close()
