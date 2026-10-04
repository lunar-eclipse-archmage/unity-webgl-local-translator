"""Run: python3 -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import manual_import
from modules.common import write_json,read_json,digest
from modules.translation_validation import validate_task

class ManualImportTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.work=Path(self.directory.name)
        self.rows=[{'id':str(i),'source':'原文'+str(i),'asset':'asset','path_id':'1','mode':'typetree','path':['values',i]} for i in range(2)]
        write_json(self.work/'extracted.json',{'file':'test.bundle','source_sha256':'source','rows':self.rows})
        write_json(self.work/'pending.json',{'rows':self.rows})
        write_json(self.work/'blocked.json',{'reason':'initial request failed','source_sha256':'source'})

    def run_import(self,rows):
        provided=self.work/'edited.json';write_json(provided,{'rows':rows})
        with patch.object(sys,'argv',['manual_import.py',str(self.work),str(provided)]), patch.object(manual_import,'log'), patch('urllib.request.urlopen',side_effect=AssertionError('API must not be called')) as api:
            manual_import._main()
            api.assert_not_called()

    def test_partial_then_complete_without_cache(self):
        self.run_import([{**self.rows[0],'translation':'译文0'}])
        self.assertEqual([x['id'] for x in read_json(self.work/'pending.json')['rows']],['1'])
        self.assertTrue((self.work/'blocked.json').exists())
        self.assertFalse((self.work/'translated.json').exists())
        with self.assertRaises(ValueError):validate_task(self.work)
        self.run_import([{**self.rows[1],'translation':'译文1'}])
        self.assertFalse((self.work/'blocked.json').exists())
        self.assertEqual(read_json(self.work/'pending.json')['rows'],[])
        self.assertEqual([r['translation'] for r in validate_task(self.work)['rows']],['译文0','译文1'])

    def test_all_rows_without_cache(self):
        self.run_import([{**r,'translation':'译文'+r['id']} for r in self.rows])
        self.assertEqual(len(validate_task(self.work)['rows']),2)
        cfg=manual_import.cfg
        glossary=read_json(manual_import.ROOT/cfg.GLOSSARY_FILE)
        expected=digest(json.dumps({'model':cfg.MODEL,'target':cfg.TARGET_LANGUAGE,'glossary':glossary,'prompt_version':manual_import.PROMPT_VERSION,'reasoning_effort':getattr(cfg,'REASONING_EFFORT',None)},sort_keys=True,ensure_ascii=False).encode())
        self.assertEqual(read_json(self.work/'translation_cache.json')['fingerprint'],expected)

    def test_invalid_source_does_not_create_cache(self):
        with self.assertRaises(ValueError):
            self.run_import([{**self.rows[0],'source':'changed','translation':'译文'}])
        self.assertFalse((self.work/'translation_cache.json').exists())
        self.assertTrue((self.work/'blocked.json').exists())

if __name__=='__main__':unittest.main()
