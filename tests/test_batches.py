import unittest
from types import SimpleNamespace
from unittest.mock import patch
from emart24.batches import process_batches


def row(product,qty=1):
    result=[None]*15
    result[0]='7F';result[1]='001';result[3]='normal';result[4]='20261013'
    result[6]=product;result[11]=qty;result[14]=1
    return result


class BatchProcessing(unittest.TestCase):
    cfg={'source_headers':[],'target':'unused','sheet':'DB'}

    def test_both_successful_files_are_imported(self):
        batches=[(SimpleNamespace(number=1,count=1),'a'),(SimpleNamespace(number=2,count=1),'b')]
        with patch('emart24.batches.read_source',side_effect=[('s',[row('a')]),('s',[row('b')])]),patch('emart24.batches.read_xlsx',return_value=('DB',[],[])),patch('emart24.batches.import_file',return_value={'status':'committed','rows':1}) as write:
            result=process_batches(self.cfg,batches,'2026-10-10')
        self.assertEqual([r['transfer'] for r in result['results']],[1,2])
        self.assertEqual(write.call_count,2)

    def test_ambiguous_revision_cannot_overwrite_or_append(self):
        with patch('emart24.batches.read_source',return_value=('s',[row('a',9)])),patch('emart24.batches.read_xlsx',return_value=('DB',[],[row('a',1)])),patch('emart24.batches.import_file') as write:
            result=process_batches(self.cfg,[(SimpleNamespace(number=1,count=1),'a')],'2026-10-10')
        write.assert_not_called()
        self.assertEqual(len(result['errors']),1)

    def test_wrong_count_cannot_import(self):
        with patch('emart24.batches.read_source',return_value=('s',[row('a')])),patch('emart24.batches.import_file') as write:
            result=process_batches(self.cfg,[(SimpleNamespace(number=1,count=2),'a')],'2026-10-10')
        write.assert_not_called()
        self.assertEqual(len(result['errors']),1)

    def test_preview_is_forwarded_to_every_import(self):
        with patch('emart24.batches.read_source',return_value=('s',[row('a')])),patch('emart24.batches.read_xlsx',return_value=('DB',[],[])),patch('emart24.batches.import_file',return_value={'status':'would_append'}) as write:
            process_batches(self.cfg,[(SimpleNamespace(number=1,count=1),'a')],'2026-10-10',dry_run=True)
        self.assertTrue(write.call_args.kwargs['dry_run'])
