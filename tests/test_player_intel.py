import csv, io, os, tempfile, unittest, json
from datetime import date, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import core, player_intel as pi
from backend.main import app, Settings

def csv_bytes(rows):
    buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);return buf.getvalue().encode()

def nba():
    return csv_bytes([{'athlete_display_name':'Test Player','athlete_id':'7','game_id':i,'game_date':f'2026-11-{i:02}','season_type':2,'minutes':'24:30','points':i,'rebounds':3,'assists':4,'team_display_name':'Example','did_not_play':'false'} for i in range(1,11)]+[{'athlete_display_name':'Test Player','athlete_id':'7','game_id':11,'game_date':'2026-11-11','season_type':2,'minutes':'0','points':0,'rebounds':0,'assists':0,'team_display_name':'Example','did_not_play':'true'}])

class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32});self.env.start();self.c=TestClient(app);self.h={'X-Local-Token':'a'*32}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_seasons(self):
        self.assertEqual(pi.season_for('NBA',date(2026,11,1)),2027);self.assertEqual(pi.season_for('NFL',date(2027,2,1)),2026);self.assertEqual(pi.season_for('MLB',date(2027,1,1)),2026)
    def test_nba(self):
        p=pi.parse_games(nba(),'NBA','Test Player',2027);self.assertEqual(p['sample'],10);self.assertEqual(p['metrics'][0]['recent_avg'],8);self.assertEqual(p['metrics'][0]['previous_avg'],3);self.assertEqual(p['metrics'][3]['season_avg'],24.5)
    def test_nfl(self):
        rows=[{'player_display_name':'Test QB','player_id':'x','week':i,'season_type':'REG','position':'QB','team':'ABC','passing_yards':i*10,'passing_tds':1,'passing_interceptions':0,'rushing_yards':2} for i in range(1,9)]
        p=pi.parse_games(csv_bytes(rows),'NFL','Test QB',2026);self.assertEqual(p['sample'],8);self.assertEqual(p['metrics'][0]['recent_avg'],60);self.assertEqual(p['metrics'][0]['previous_avg'],20)
    def test_exact_names(self):
        with self.assertRaises(RuntimeError):pi.parse_games(nba(),'NBA','Player',2027)
    @patch('backend.player_intel._fetch')
    def test_cache_and_quota(self,f):
        f.return_value=nba();payload={'player':'Test Player','league':'NBA','season':2027}
        with patch('backend.player_intel.season_for',return_value=2027):
            a=self.c.post('/api/player-research',headers=self.h,json=payload);self.assertEqual(a.status_code,200,a.text)
            b=self.c.post('/api/player-research',headers=self.h,json=payload);self.assertEqual(b.json()['origin'],'cache')
            self.assertEqual(f.call_count,1);self.assertEqual(core.used(),0)
            f.side_effect=RuntimeError('offline');payload['refresh']=True
            d=self.c.post('/api/player-research',headers=self.h,json=payload);self.assertTrue(d.json()['stale'])
    @patch('backend.player_intel._fetch')
    def test_mlb(self,f):
        f.side_effect=[json.dumps({'people':[{'id':1,'fullName':'Test Hitter'}]}).encode(),json.dumps({'stats':[{'splits':[{'date':'2026-04-01','game':{'gamePk':1},'stat':{'hits':2,'homeRuns':1,'rbi':1,'stolenBases':0}}]}]}).encode(),b'{"stats":[]}']
        p=pi.mlb_fetch('Test Hitter',2026);self.assertEqual(p['metrics'][0]['season_avg'],2);self.assertEqual(p['sample'],'hitting: 1')
    def test_hold_scenarios(self):
        s=Settings().model_dump();r=pi.hold_scenarios(50,s,3,15,[-50,0,50]);self.assertLess(r[0]['max_bid'],r[1]['max_bid']);self.assertLess(r[1]['max_bid'],r[2]['max_bid']);self.assertEqual(r[1]['exit_price'],50);self.assertEqual(pi.hold_scenarios(1,s,3,15,[-100,0,50])[0]['max_bid'],0)
        self.assertLess(pi.hold_scenarios(50,s,5,15,[-50,0,50])[1]['max_bid'],r[1]['max_bid'])
    def test_auth(self):
        self.assertEqual(self.c.post('/api/player-research',json={'player':'Test Player','league':'NBA'}).status_code,401)
        self.assertEqual(self.c.post('/api/hold-scenarios',headers=self.h,json={'median':50,'settings':{},'years':0,'annual_target':15,'bear':-50,'bull':50}).status_code,422)
