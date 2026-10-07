import json
import sqlite3
from pathlib import Path

from .core import StopRun, file_hash, fingerprint, now_kst
from .workbooks import read_xlsx


class Ledger:
    def __init__(self, path, readonly=False):
        self.readonly = readonly
        path = Path(path)
        if readonly and not path.exists():
            self.db = sqlite3.connect(":memory:")
        elif readonly:
            self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        if not readonly or not path.exists():
            self.db.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, target TEXT NOT NULL, day TEXT NOT NULL,
                transfer TEXT, source_hash TEXT, data_hash TEXT NOT NULL,
                status TEXT NOT NULL, start_row INTEGER, row_count INTEGER,
                before_hash TEXT, after_hash TEXT, backup TEXT, created TEXT NOT NULL)""")
            self.db.commit()

    def close(self):
        self.db.close()

    def records(self, target):
        return self.db.execute("SELECT * FROM runs WHERE target=? ORDER BY created", (str(Path(target).resolve()).casefold(),)).fetchall()

    def put(self, **values):
        if self.readonly:
            raise StopRun("미리보기에서는 이력을 기록하지 않습니다.")
        values["target"] = str(Path(values["target"]).resolve()).casefold()
        values["created"] = now_kst().isoformat()
        keys = list(values)
        self.db.execute(f"INSERT INTO runs ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [values[k] for k in keys])
        self.db.commit()

    def status(self, run_id, state):
        if self.readonly:
            return
        self.db.execute("UPDATE runs SET status=? WHERE id=?", (state, run_id))
        self.db.commit()

    def recover(self, target, sheet):
        for r in self.records(target):
            if r["status"] != "prepared":
                continue
            current = file_hash(target)
            if current == r["before_hash"]:
                self.status(r["id"], "aborted")
            elif current == r["after_hash"]:
                _, _, rows = read_xlsx(target, sheet)
                batch = rows[r["start_row"]-2:r["start_row"]-2+r["row_count"]]
                if len(batch) != r["row_count"] or fingerprint(batch) != r["data_hash"]:
                    raise StopRun("복구 검증 실패: 저장된 추가 영역이 다릅니다.")
                self.status(r["id"], "committed")
            else:
                raise StopRun("미완료 저장 이후 대상 파일이 변경됐습니다. 백업과 이력을 확인하세요.")

    def previous(self, target, day, transfer, digest):
        for r in self.records(target):
            if r["status"] not in ("committed", "existing"):
                continue
            if transfer and r["transfer"] == transfer:
                if r["data_hash"] != digest:
                    raise StopRun("같은 전송번호의 내용이 변경됐습니다. 확인이 필요합니다.")
                return True
            if r["day"] == day:
                if r["data_hash"] != digest:
                    raise StopRun("이미 처리한 날짜의 수정본입니다. 자동 추가하지 않습니다.")
                return True
        return False
