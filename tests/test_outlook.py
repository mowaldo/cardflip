import unittest, os, tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import outlook, core
from backend.main import app

DATA=b'full_name,week,date_modified,report_status,practice_status,report_primary_injury,gsis_id\nTest Player,9,2026-11-01,Out,Limited,Knee,x\nTest Player,10,2026-11-08,Questionable,Full,Knee,x\nOther Player,11,2026-11-15,Out,Limited,Ankle,y\n'
class OutlookTests(unittest.TestCase):
    def test_report(self):
        r=outlook.parse_injuries(DATA,'Test Player');self.assertEqual(r['status'],'Older report only');self.assertEqual(r['report']['report_status'],'Questionable');self.assertEqual(r['latest_week'],11)
        self.assertIsNone(outlook.parse_injuries(DATA,'Missing Player')['report'])
    def test_ambiguous(self):
        with self.assertRaises(RuntimeError):outlook.parse_injuries(DATA+b'Test Player,11,2026-11-15,Out,Limited,Ankle,z\n','Test Player')
    def test_momentum(self):
        m={'label':'Passing yards','recent_n':5,'previous_n':5,'recent_avg':300,'previous_avg':240}
        d={'league':'NFL','season':2026,'metrics':[m]}
        with patch('backend.player_intel.season_for',return_value=2026):
            self.assertEqual(outlook.performance(d)['label'],'Production rising');d['stale']=True;self.assertEqual(outlook.performance(d)['label'],'Historical / stale');d['stale']=False;m['previous_n']=3;self.assertEqual(outlook.performance(d)['label'],'Limited sample')
    def test_cache(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'CARDFLIP_DB':tmp+'/test.db','LOCAL_TOKEN':'a'*32}),patch('backend.player_intel._fetch',return_value=DATA) as fetch,patch('backend.player_intel.season_for',return_value=2026):
            c=TestClient(app);h={'X-Local-Token':'a'*32};p={'player':'Test Player','league':'NFL','season':2026}
            self.assertEqual(c.post('/api/nfl-injury',json=p).status_code,401)
            r=c.post('/api/nfl-injury',headers=h,json=p);self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(c.post('/api/nfl-injury',headers=h,json=dict(p,player='Other Player')).status_code,200);self.assertEqual(fetch.call_count,1);self.assertEqual(core.used(),0)
