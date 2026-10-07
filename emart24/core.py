from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))


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


def load_config(path):
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    for key in ("target", "runtime"):
        p = Path(cfg[key])
        cfg[key] = str(p if p.is_absolute() else path.parent / p)
    return cfg
