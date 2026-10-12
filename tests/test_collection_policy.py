import unittest
from datetime import date,datetime
from emart24.core import Transfer,select_transfers,config_hash,site_verification_matches
from emart24.collection_calendar import collection_dates,polling_slots


class CollectionPolicy(unittest.TestCase):
    def test_schedule_only_change_preserves_site_proof_but_path_change_does_not(self):
        old={'start':'10:30','deadline':'11:00','retry_seconds':300,'target':'old.xlsx','site':{'url':'test'}}
        stamp={'config_hash':config_hash(old)}
        updated=dict(old,start='10:40',deadline='11:10')
        self.assertTrue(site_verification_matches(updated,stamp))
        self.assertFalse(site_verification_matches(dict(updated,target='different.xlsx'),stamp))
        self.assertFalse(site_verification_matches(dict(updated,site={'url':'changed'}),stamp))
    def test_main_and_supplement_are_both_selected(self):
        day=date(2026,10,10)
        def entry(number,count,errors,hour,minute):
            return Transfer(number,'10월 10일 7F 주문정보(7F 이마트24) 전송',
                            'source.xlsx',count,errors,datetime(2026,10,10,hour,minute))
        main=entry(2820901,73,0,10,52)
        failed=entry(2820902,0,2,11,5)
        extra=entry(2820903,2,0,11,6)
        self.assertEqual(select_transfers([extra,failed,main],day),[main,extra])

    def test_slots_include_saturday_and_final_eleven(self):
        slots=polling_slots(date(2026,10,10))
        self.assertEqual([s.strftime('%H:%M') for s in slots],['10:40','10:45','10:50','10:55','11:00','11:05','11:10'])
        self.assertTrue(all(s.utcoffset().total_seconds()==32400 for s in slots))
        self.assertEqual(polling_slots(date(2026,10,11)),[])

    def test_recovery_is_chronological_and_skips_only_sunday(self):
        self.assertEqual(collection_dates(date(2026,10,8),date(2026,10,12)),
                         [date(2026,10,8),date(2026,10,9),date(2026,10,10),date(2026,10,12)])
        self.assertEqual(collection_dates(date(2026,10,12),date(2026,10,8)),[])
