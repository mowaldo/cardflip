import os,tempfile,unittest,json,csv,io
from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import core,workspace,prospect,board
from backend.main import app,Settings
from test_v09 import CARD,sale
class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/db.sqlite','LOCAL_TOKEN':'a'*32,'COMPSAPI_KEY':'fake'});self.env.start();self.c=TestClient(app);self.h={'X-Local-Token':'a'*32}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def post(self,path,data):return self.c.post('/api/'+path,json=data,headers=self.h)
    def get(self,path):return self.c.get('/api/'+path,headers=self.h)
    def entry(self,mode='paper'):
        return {'card':dict(CARD,variant='Base',grade_label='PSA 10'),'mode':mode,'paid':10,'inbound':2,'tax':1,'net_value':20,'confirmed':True}
    def test_history_clear_preserves_cache_and_inventory(self):
        with patch('backend.provider.fetch_board',return_value=[sale(1)]):
            self.assertEqual(self.post('board',{'card':CARD}).status_code,200)
        self.assertEqual(len(self.get('history').json()['rows']),1);self.assertEqual(self.post('inventory/add',self.entry()).status_code,200)
        self.post('history/clear',{});self.assertEqual(self.get('history').json()['rows'],[]);self.assertIsNotNone(core.get_cache(board.key(CARD)));self.assertEqual(self.get('inventory?mode=paper').json()['summary']['owned'],1);self.assertEqual(core.used(),1)
    def test_history_does_not_reuse_variant_for_new_scan(self):
        workspace.record(dict(CARD,variant='Silver',grader='PSA',grade='10'),'scan');workspace.record(dict(CARD,grader='RAW'),'scan');workspace.record(CARD,'price board');r=workspace.history()[0];self.assertEqual(r['card']['variant'],'');self.assertEqual(r['card']['grader'],'RAW')
    def test_portfolio_actual_separate_and_math(self):
        a=self.post('inventory/add',self.entry()).json()['id'];b=self.post('inventory/add',self.entry('real')).json()['id'];self.assertNotEqual(a,b)
        self.assertEqual(self.get('inventory?mode=paper').json()['summary']['unrealized'],7)
        self.assertEqual(self.post('inventory/sell',{'id':a,'gross':30,'selling':4,'outbound':3,'other':1}).status_code,200)
        d=self.get('inventory?mode=paper').json();self.assertEqual(d['summary']['realized'],9);self.assertEqual(d['rows'][0]['net'],22);self.assertEqual(self.get('inventory?mode=real').json()['summary']['owned'],1)
        self.assertEqual(self.post('inventory/sell',{'id':a,'gross':40,'selling':0,'outbound':0}).status_code,404)
        self.assertEqual(self.post('inventory/mark',{'id':a,'net_value':40}).status_code,404)
    def test_mark_unpriced_and_delete(self):
        a=self.post('inventory/add',self.entry()).json()['id'];self.post('inventory/mark',{'id':a,'net_value':None});d=self.get('inventory?mode=paper').json()['summary'];self.assertIsNone(d['unrealized']);self.assertEqual(d['open_cost'],13);self.post('inventory/delete',{'id':a});self.assertEqual(self.get('inventory?mode=paper').json()['rows'],[])
    def test_validation_and_auth(self):
        self.assertEqual(self.c.get('/api/history').status_code,401);x=self.entry();x['card']['variant']='Unspecified';self.assertEqual(self.post('inventory/add',x).status_code,422);x=self.entry();x['paid']=-1;self.assertEqual(self.post('inventory/add',x).status_code,422)
    def test_replay_no_future_leakage(self):
        rows=[{'price':50,'shipping':0,'date':(core.now()-timedelta(days=30-i)).isoformat(),'title':'Base PSA 10'} for i in range(6)]
        rows.append({'price':10,'shipping':0,'date':(core.now()-timedelta(days=20)).isoformat(),'title':'Base PSA 10'});rows.append({'price':45,'shipping':0,'date':(core.now()-timedelta(days=10)).isoformat(),'title':'Base PSA 10'})
        a=workspace.replay(rows,Settings().model_dump(),7);self.assertEqual(a['closed'],1);self.assertGreater(a['profit'],0);self.assertEqual(workspace.replay(rows[:-1],Settings().model_dump(),7)['pending'],1);self.assertEqual(workspace.replay(rows[-2:],Settings().model_dump(),7)['closed'],0)
    def test_replay_endpoint_uses_cache_and_confirmation(self):
        items=[sale(i,age=30-i,price=50) for i in range(6)]+[sale(6,age=20,price=10),sale(7,age=10,price=45)]
        with patch('backend.provider.fetch_board',return_value=items):self.post('board',{'card':CARD})
        r={'card':CARD,'number':'211','variant':'Base','grade':'PSA 10','confirmed':False};self.assertIsNone(self.post('card-research',r).json()['replay']);r['confirmed']=True;self.assertEqual(self.post('card-research',r).json()['replay']['closed'],1);self.assertEqual(core.used(),1)
    @patch('backend.player_intel._fetch')
    def test_career_nfl_nba_mlb(self,f):
        f.return_value=b'display_name,birth_date,rookie_season,draft_year,draft_pick,position\nTest QB,2000-01-01,2023,2023,10,QB\n';r=self.post('career',{'player':'Test QB','league':'NFL'}).json();self.assertEqual(r['draft_pick'],10);self.assertEqual(self.post('career',{'player':'Test QB','league':'NFL'}).json()['origin'],'cache')
        f.return_value=b'athlete_display_name,athlete_date_of_birth,athlete_draft_year\nTest NBA,2002-01-01,2025\n';self.assertEqual(self.post('career',{'player':'Test NBA','league':'NBA'}).json()['draft_year'],2025)
        f.return_value=json.dumps({'people':[{'fullName':'Test MLB','birthDate':'2003-01-01','mlbDebutDate':'2025-06-01'}]}).encode();self.assertEqual(self.post('career',{'player':'Test MLB','league':'MLB'}).json()['debut'],'2025-06-01');self.assertEqual(core.used(),0)
    @patch('backend.player_intel._fetch')
    def test_minor_sport_guard(self,f):
        f.side_effect=[json.dumps({'people':[{'fullName':'Test MLB','id':9}]}).encode(),json.dumps({'stats':[{'splits':[{'sport':{'id':12},'stat':{'ops':'.850','gamesPlayed':20}},{'sport':{'id':1},'stat':{'ops':'.999'}},{'stat':{'ops':'.999'}}]}]}).encode(),b'{"stats":[]}']
        r=self.post('minor-stats',{'player':'Test MLB','league':'MLB'}).json();self.assertEqual(len(r['rows']),1);self.assertEqual(r['rows'][0]['level'],'Double-A');self.assertEqual(core.used(),0)
