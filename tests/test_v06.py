import os,tempfile,unittest
from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import core,variants,vision,provider
from backend.main import app
from test_app import CARD,sale
from test_v05 import JORDAN

class TestFamily(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32,'COMPSAPI_KEY':'fake-key','MONTHLY_LIMIT':'100'});self.env.start();self.client=TestClient(app);self.headers={'X-Local-Token':'a'*32}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def post(self,path,data):return self.client.post('/api/'+path,json=data,headers=self.headers)
    def data(self):
        return [sale(i,30,'2020 Panini Prizm Anthony Edwards #258 PSA 10 Base') for i in range(1,7)]+[sale(i,80,'2020 Panini Prizm Anthony Edwards #258 PSA 10 Silver') for i in range(7,13)]+[sale(13,25),sale(14,900,'2020 Panini Prizm Anthony Edwards #258 PSA 10 Genesis /99'),sale(15,300,'2020 Panini Prizm Anthony Edwards #258 PSA 10 autograph'),sale(16,200,'2020 Panini Prizm Anthony Edwards #258 PSA 10 Silver Gold'),sale(17,200,'2020 Panini Prizm Anthony Edwards #258 PSA 10 Blue'),sale(18,200,'2020 Panini Prizm Anthony Edwards #258 PSA 10 Base Silver'),sale(19,200,'2020 Panini Prizm Anthony Edwards #258 PSA 10 lot')]
    @patch('backend.provider.fetch')
    def test_family_separates_and_reuses(self,fetch):
        fetch.return_value=self.data();card=dict(CARD,variant='Unknown');r=self.post('family',{'card':card}).json();g={x['variant']:x for x in r['groups']};self.assertEqual(set(g),{'Base','Silver','Unspecified'});self.assertEqual(g['Base']['median'],30);self.assertEqual(g['Silver']['median'],80);self.assertIsNone(g['Unspecified']['max_bid']);self.assertEqual(r['recommendation'],'VERIFY VARIANT — PASS');self.assertEqual(core.used(),1);fetch.assert_called_once_with(dict(card,grade_type=''),broad=True)
        self.assertEqual(self.post('family',{'card':card}).json()['origin'],'cache');r=self.post('lookup',{'card':dict(CARD,variant='Silver')}).json();self.assertEqual(r['origin'],'family cache');self.assertEqual(len(r['rows']),6);self.assertEqual(core.used(),1)
        e=self.post('evaluate',{'key':r['key'],'selected':[],'settings':{'bid':1},'preview':True}).json();self.assertEqual(e['recommendation'],'PREVIEW — UNVERIFIED')
        b=self.post('lookup',{'card':CARD}).json();self.assertEqual(len(b['rows']),7);self.assertEqual(b['fetched'],r['fetched']);self.assertEqual(fetch.call_count,1)
    @patch('backend.provider.fetch')
    def test_stale_family_no_bid(self,fetch):
        fetch.return_value=self.data();card=dict(CARD,variant='Unknown');self.post('family',{'card':card});
        with core.connection() as c:c.execute('UPDATE cache SET fetched=?',((core.now()-timedelta(days=2)).isoformat(),))
        with patch.dict(os.environ,{'MONTHLY_LIMIT':'1'}):
            r=self.post('family',{'card':card}).json();self.assertTrue(r['stale']);self.assertTrue(all(g['max_bid'] is None for g in r['groups']));self.assertEqual(fetch.call_count,1)
    def test_grade_and_duplicate_filter(self):
        items=self.data();bad=sale(55);bad['card']['grade']='9';g=variants.groups(items+[bad,items[0]],CARD);self.assertEqual(len(g['Base']),6);self.assertEqual(len(g['Unspecified']),1)
    def test_remember_and_conflict(self):
        result=vision.normalize(JORDAN);card=dict(result['fields'],variant='Base');self.assertEqual(self.post('remember',{'card':card,'cert':'53353413','confirmed':False}).status_code,422);self.assertEqual(self.post('remember',{'card':card,'cert':'53353413','confirmed':True}).status_code,200)
        r=variants.recall(result);self.assertTrue(r['remembered']);self.assertTrue(r['auto_eligible']);self.assertEqual(r['fields']['variant'],'Base');self.assertEqual(core.used(),0)
        for raw in (dict(JORDAN,n='212'),dict(JORDAN,v='Silver'),dict(JORDAN,d=9),dict(JORDAN,a=True)):
            self.assertFalse(variants.recall(vision.normalize(raw)).get('remembered',False))
    @patch('backend.provider.requests.get')
    def test_provider_broad(self,get):
        get.return_value.status_code=200;get.return_value.json.return_value={'items':[]};provider.fetch(dict(CARD,variant='Unknown'),broad=True);p=get.call_args.kwargs['params'];self.assertNotIn('Unknown',p['q']);self.assertEqual(p['size'],240)
    def test_auth(self):
        self.assertEqual(self.client.post('/api/family',json={'card':dict(CARD,variant='Unknown')}).status_code,401)
        self.assertEqual(self.client.post('/api/remember',json={'card':CARD,'cert':'12345678','confirmed':True}).status_code,401)
