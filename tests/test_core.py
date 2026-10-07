import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from emart24.core import KST, Retryable, StopRun, Transfer, choose_transfer, fingerprint, overlap, trim_rows, within_window
from emart24.ledger import Ledger
from emart24.site import parse_transfer


class BusinessRules(unittest.TestCase):
    def transfer(self, number, stamp="2026-10-06 10:30:00", count=73, errors=0, title="10월 06일 7F 주문정보(7F 이마트24) 전송"):
        return Transfer(number, title, "orders.xlsx", count, errors, datetime.fromisoformat(stamp))

    def test_select_latest_valid_not_latest_invalid(self):
        items = [self.transfer(1), self.transfer(2), self.transfer(3, count=0),
                 self.transfer(4, errors=1), self.transfer(5, stamp="2025-10-06 11:00:00"),
                 self.transfer(6, title="10월 06일 7F 입고정보 전송")]
        self.assertEqual(choose_transfer(items, date(2026,10,6)).number, 2)

    def test_padding_whitespace_and_no_match(self):
        i = self.transfer(1, title="10월 6일   7F 주문정보 (7F 이마트24) 전송")
        self.assertEqual(choose_transfer([i],date(2026,10,6)), i)
        with self.assertRaises(Retryable):
            choose_transfer([i], date(2026,10,7))

    def test_internal_blanks_preserved(self):
        self.assertEqual(trim_rows([[1],[None],[2],[None]]), [[1],[None],[2]])

    def test_multiset_overlap_preserves_repeated_orders(self):
        self.assertEqual(overlap([[1],[1]],[[1]]), "partial")
        self.assertEqual(overlap([[1],[1]],[[1],[1],[2]]), "all")
        self.assertEqual(overlap([[1]],[[2]]), "none")

    def test_identifiers_are_not_numbers(self):
        self.assertNotEqual(fingerprint([["001"]]),fingerprint([[1]]))
        self.assertEqual(fingerprint([[1.0]]),fingerprint([[1]]))

    def test_schedule_boundaries_weekends_timezone(self):
        for hour, minute, expected in [(10,29,False),(10,30,True),(11,0,True),(11,1,False)]:
            self.assertEqual(within_window(datetime(2026,10,7,hour,minute,tzinfo=KST)),expected)
        self.assertFalse(within_window(datetime(2026,10,10,10,30,tzinfo=KST)))

    def test_parse_rendered_row(self):
        cells = ["2818194","10월 06일 7F 주문정보(7F 이마트24) 전송","주문정보","orders.xlsx","73","0","0","0","2026-10-06 10:29:41"]
        self.assertEqual(parse_transfer(cells).count,73)
        self.assertIsNone(parse_transfer(["번호","제목"]))
        cells[4] = "unknown"
        with self.assertRaises(StopRun):
            parse_transfer(cells)


class HistoryRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.target = self.path / "target.xlsx"
        self.ledger = Ledger(self.path / "history.sqlite3")

    def tearDown(self):
        self.ledger.close()
        self.tmp.cleanup()

    def add(self, status="committed", **kwargs):
        self.ledger.put(id="one",target=str(self.target),day="2026-10-06",transfer="123",data_hash=fingerprint([[1]]),status=status,**kwargs)

    def test_repeat_and_revision(self):
        self.add()
        self.assertTrue(self.ledger.previous(self.target,"2026-10-06","124",fingerprint([[1]])))
        with self.assertRaises(StopRun):
            self.ledger.previous(self.target,"2026-10-06","124",fingerprint([[2]]))

    def test_crash_before_replace_aborts(self):
        self.add("prepared", before_hash="old",after_hash="new",start_row=2,row_count=1)
        with patch("emart24.ledger.file_hash",return_value="old"):
            self.ledger.recover(self.target,"DB")
        self.assertEqual(self.ledger.records(self.target)[0]["status"],"aborted")

    def test_crash_after_replace_commits(self):
        self.add("prepared", before_hash="old",after_hash="new",start_row=2,row_count=1)
        with patch("emart24.ledger.file_hash",return_value="new"), patch("emart24.ledger.read_xlsx",return_value=("DB",[],[[1]])):
            self.ledger.recover(self.target,"DB")
        self.assertEqual(self.ledger.records(self.target)[0]["status"],"committed")

    def test_external_edit_during_recovery_stops(self):
        self.add("prepared", before_hash="old",after_hash="new",start_row=2,row_count=1)
        with patch("emart24.ledger.file_hash",return_value="different"), self.assertRaises(StopRun):
            self.ledger.recover(self.target,"DB")

    def test_dry_run_does_not_create_database(self):
        path = self.path / "absent.sqlite3"
        ledger = Ledger(path, readonly=True)
        self.assertEqual(ledger.records(self.target),[])
        ledger.close()
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
