from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime, time as daytime
from pathlib import Path

from .core import DEFAULT_CONFIG, TARGET_FILENAME, KST, Retryable, StopRun, config_hash, load_config, now_kst, save_target_directory, within_window
from .importer import import_file
from .windows import notify, run_lock, set_credential


def main():
    parser = argparse.ArgumentParser(description="이마트24 주문 자동 적재")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--date", type=date.fromisoformat)
    run.add_argument("--source", type=Path, help="사이트 대신 지정한 로컬 원본 사용")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--scheduled", action="store_true")
    run.add_argument("--notify", action="store_true")
    sub.add_parser("credentials")
    sub.add_parser("check-ready")
    sub.add_parser("show-config")
    configure = sub.add_parser("configure", help="PC별 대상 파일 폴더 설정")
    configure.add_argument("--target-dir", help="고정 파일명이 있는 폴더. 생략하면 폴더 선택 창 표시")
    verify = sub.add_parser("verify-site")
    verify.add_argument("--date", type=date.fromisoformat, default=now_kst().date())
    args = parser.parse_args()
    try:
        if args.command == "configure":
            folder = args.target_dir
            if folder is None:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                try:
                    folder = filedialog.askdirectory(title=f"{TARGET_FILENAME} 파일이 있는 폴더 선택", mustexist=True)
                finally:
                    root.destroy()
                if not folder:
                    print("폴더 설정을 취소했습니다. 기존 설정은 유지됩니다.")
                    return 0
            print(f"대상 파일 설정 완료: {save_target_directory(args.config, folder)}")
            return 0
        cfg = load_config(args.config)
    except (StopRun, OSError, ValueError) as exc:
        print(f"설정 오류: {exc}", file=sys.stderr)
        return 2
    if args.command == "show-config":
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0
    runtime = Path(cfg["runtime"])
    runtime.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=runtime / "events.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    if args.command == "credentials":
        set_credential(cfg["credential_name"])
        return 0
    if args.command == "check-ready":
        from .ledger import Ledger
        stamp_path = runtime / "site_verified.json"
        if not stamp_path.exists():
            print("사이트 연결 검증이 필요합니다.", file=sys.stderr)
            return 2
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        if stamp["config_hash"] != config_hash(cfg):
            print("설정 변경 후 사이트 검증이 필요합니다.", file=sys.stderr)
            return 2
        ledger = Ledger(runtime / "history.sqlite3", readonly=True)
        try:
            records = ledger.records(cfg["target"])
            ready = any(r["status"] in ("committed", "existing") for r in records) and not any(r["status"] == "prepared" for r in records)
        finally:
            ledger.close()
        if not ready:
            print("운영 파일 첫 실행과 복구 확인이 필요합니다.", file=sys.stderr)
            return 2
        print("예약 등록 전 검증을 통과했습니다.")
        return 0
    if args.command == "run" and args.scheduled and (args.source or args.date or args.dry_run):
        parser.error("--scheduled는 --source, --date, --dry-run과 함께 사용할 수 없습니다.")
    scheduled = args.command == "run" and args.scheduled
    day = getattr(args, "date", None) or now_kst().date()
    deadline = datetime.combine(day, daytime.fromisoformat(cfg["deadline"]), KST)
    try:
        if not Path(cfg["target"]).is_file():
            raise StopRun(f"설정한 대상 파일이 없습니다: {cfg['target']}")
        with run_lock(runtime / "run.lock"):
            if scheduled and not within_window(now_kst(), cfg["start"], cfg["deadline"]):
                print("예약 실행 시간 밖입니다. 적재하지 않았습니다.")
                return 0
            while True:
                try:
                    transfer = None
                    if args.command == "verify-site" or not args.source:
                        from .site import fetch
                        item, source = fetch(cfg, day)
                        transfer = item.number
                    else:
                        source = args.source
                    dry = args.command == "verify-site" or args.dry_run
                    result = import_file(cfg, source, day, transfer, dry_run=dry)
                    logging.info("result %s", json.dumps(result, ensure_ascii=False))
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    if args.command == "verify-site":
                        stamp = {"verified_at": now_kst().isoformat(), "config_hash": config_hash(cfg),
                                 "transfer": transfer, "result": result}
                        (runtime / "site_verified.json").write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding="utf-8")
                    if scheduled or getattr(args, "notify", False):
                        notify(f"{day}: {result['status']} ({result['rows']}행).")
                    return 0
                except Retryable as exc:
                    logging.warning("retryable %s", exc)
                    if not scheduled or now_kst() >= deadline:
                        raise
                    delay = min(cfg["retry_seconds"], max(0, (deadline-now_kst()).total_seconds()))
                    time.sleep(delay)
    except StopRun as exc:
        logging.error("stopped %s", exc)
        print(str(exc), file=sys.stderr)
        if scheduled or getattr(args, "notify", False):
            notify(f"이마트24 자동화 중단: {exc}")
        return 2
    except Exception as exc:
        # Avoid dumping site URLs or credential-bearing library exceptions.
        logging.error("unexpected error type=%s", type(exc).__name__)
        print(f"예상하지 못한 오류({type(exc).__name__}). 원본 파일은 보존되며 로그를 확인하세요.", file=sys.stderr)
        if scheduled or getattr(args, "notify", False):
            notify(f"이마트24 자동화 오류: {type(exc).__name__}. 로그를 확인하세요.")
        return 3


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
