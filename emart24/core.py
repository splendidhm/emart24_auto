from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
TARGET_FILENAME = "재고관리_이마트24_26년(신제품 추가).xlsx"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.json"


class StopRun(Exception):
    """Non-retryable validation or operator intervention."""


class Retryable(StopRun):
    pass


def now_kst():
    return datetime.now(KST)


def compact(value):
    return re.sub(r"\s+", "", str(value or ""))


def cell(value):
    # Excel dates remain serial values for Value2; retain identifier strings.
    if isinstance(value, (datetime, date)):
        from openpyxl.utils.datetime import to_excel
        return to_excel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StopRun("유한하지 않은 숫자가 있습니다.")
        return int(value) if value.is_integer() else value
    return None if value == "" else value


def canonical(rows):
    return [[cell(v) for v in row] for row in rows]


def fingerprint(rows):
    raw = json.dumps(canonical(rows), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def trim_rows(rows):
    rows = canonical(rows)
    while rows and all(v is None for v in rows[-1]):
        rows.pop()
    return rows


def overlap(source, existing):
    # Multiset comparison keeps legitimate repetitions in the incoming file.
    incoming = Counter(tuple(r) for r in canonical(source) if any(v is not None for v in r))
    present = Counter(tuple(r) for r in canonical(existing) if any(v is not None for v in r))
    common = sum((incoming & present).values())
    if incoming and common == sum(incoming.values()):
        return "all"
    return "partial" if common else "none"


@dataclass(frozen=True)
class Transfer:
    number: int
    title: str
    filename: str
    count: int
    errors: int
    registered: datetime


def choose_transfer(items, day):
    pattern = rf"0?{day.month}월0?{day.day}일7F주문정보\(7F이마트24\)전송"
    valid = [i for i in items if re.fullmatch(pattern, compact(i.title))
             and i.registered.date() == day and i.count > 0 and i.errors == 0]
    if not valid:
        raise Retryable("당일 최신 유효 주문 항목이 아직 없습니다.")
    return max(valid, key=lambda i: (i.registered, i.number))


def within_window(now, start="10:30", deadline="11:00"):
    local = now.astimezone(KST)
    return local.weekday() < 5 and time.fromisoformat(start) <= local.time().replace(tzinfo=None) <= time.fromisoformat(deadline)


def local_config_path(path):
    path = Path(path).resolve()
    return path.with_name(path.stem + ".local.json")


def resolve_directory(value, base):
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    if re.search(r"%[^%]+%|\$\{[^}]+\}|\$[A-Za-z_][A-Za-z_0-9]*", expanded):
        raise StopRun("폴더 경로에 해석되지 않은 환경 변수가 있습니다.")
    p = Path(expanded)
    return (p if p.is_absolute() else Path(base) / p).resolve()


def save_target_directory(path, directory):
    import tempfile
    path = Path(path).resolve()
    folder = resolve_directory(directory, path.parent)
    target = folder / TARGET_FILENAME
    if not target.is_file():
        raise StopRun(f"선택한 폴더에 {TARGET_FILENAME} 파일이 없습니다.")
    local = local_config_path(path)
    # PC-specific path only. Shared business settings stay in config.json.
    payload = json.dumps({"target_directory": str(folder)}, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=local.parent, suffix=".tmp", delete=False) as f:
        f.write(payload)
        temporary = Path(f.name)
    try:
        os.replace(temporary, local)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def config_hash(cfg):
    raw = json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_config(path=DEFAULT_CONFIG):
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    local = local_config_path(path)
    if local.exists():
        override = json.loads(local.read_text(encoding="utf-8-sig"))
        if set(override) - {"target_directory"}:
            raise StopRun("PC별 설정에는 target_directory만 지정할 수 있습니다.")
        cfg.update(override)
    folder = cfg.get("target_directory")
    if not folder:
        # Existing custom configs with a full path remain usable, but the fixed
        # filename cannot silently be changed.
        legacy = cfg.get("target")
        if legacy:
            target = resolve_directory(legacy, path.parent)
            if target.name != TARGET_FILENAME:
                raise StopRun(f"대상 파일명은 {TARGET_FILENAME}로 고정되어 있습니다.")
            folder = str(target.parent)
        else:
            raise StopRun("대상 폴더를 먼저 설정하세요: configure-target.cmd 또는 configure --target-dir 폴더경로")
    folder = resolve_directory(folder, path.parent)
    cfg["target_directory"] = str(folder)
    cfg["target"] = str(folder / TARGET_FILENAME)
    cfg["runtime"] = str(resolve_directory(cfg["runtime"], path.parent))
    return cfg
