import unittest,tempfile,os
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import vision,core
from backend.main import app
from test_v05 import JORDAN
from test_app import sale

class TestRawDiscovery(unittest.TestCase):
    def test_no_rc_number_or_base_conflict(self):
        out=vision.normalize(dict(JORDAN,p='Kon Knueppel',s='NBA',y='2024',m='Panini',t='NBA Hoops Refractor',n='RC',v='Base',g='RAW',d=None,gt=None,c=None))
        self.assertNotIn('number',out['fields']);self.assertNotIn('variant',out['fields']);self.assertEqual(out['fields']['set'],'Panini NBA Hoops');self.assertEqual(out['fields']['grader'],'RAW');self.assertFalse(out['auto_eligible'])
    def test_unknown_grader_not_assumed_raw(self):
        out=vision.normalize(dict(JORDAN,g=None,d=None,c=None));self.assertNotIn('grader',out['fields']);self.assertFalse(out['auto_eligible'])
    def test_discovery_without_number_has_no_price(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'CARDFLIP_DB':d+'/test.db','LOCAL_TOKEN':'a'*32,'COMPSAPI_KEY':'fake','MONTHLY_LIMIT':'100'}):
            card=dict(year='2025',player='Kon Knueppel',set='Topps Chrome',number='',variant='Unknown',grader='RAW',grade='')
            items=[]
            for i in range(1,8):
                x=sale(i,30,f'2025 Topps Chrome Kon Knueppel #{i} Base');x['card']={'graded':False};items.append(x)
            graded=sale(8,100,'2025 Topps Chrome Kon Knueppel #8 PSA 10 Base');items.append(graded)
            client=TestClient(app);h={'X-Local-Token':'a'*32}
            with patch('backend.provider.fetch',return_value=items) as fetch:
                r=client.post('/api/family',json={'card':card},headers=h);self.assertEqual(r.status_code,200,r.text);out=r.json();self.assertEqual(out['groups'][0]['count'],7);self.assertIsNone(out['groups'][0]['median']);self.assertIsNone(out['groups'][0]['max_bid']);self.assertIn('Checklist number unknown',out['reason']);self.assertEqual(core.used(),1)
                self.assertEqual(client.post('/api/family',json={'card':card},headers=h).json()['origin'],'cache');self.assertEqual(fetch.call_count,1)
                self.assertEqual(client.post('/api/lookup',json={'card':card},headers=h).status_code,422)
                self.assertEqual(client.post('/api/lookup',json={'card':dict(card,number='RC',variant='Base')},headers=h).status_code,422)
