import os, tempfile, unittest
from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app, Settings
from backend import core

CARD={'year':'2020','player':'Anthony Edwards','set':'Panini Prizm','number':'258','variant':'Base','grader':'PSA','grade':'10'}
def sale(i,price=60,title=None):
    return {'item_id':str(i),'title':title or '2020 Panini Prizm Anthony Edwards #258 PSA 10','price':price,'shipping_cost':0,'last_sold':(core.now()-timedelta(days=i)).isoformat(),'card':{'grader':'PSA','grade':'10','card_number':'258'},'url':'https://www.ebay.com/itm/123'}
class TestApp(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32,'COMPSAPI_KEY':'fake-key','MONTHLY_LIMIT':'100'});self.env.start();self.client=TestClient(app);self.headers={'X-Local-Token':'a'*32}
    def tearDown(self): self.env.stop();self.tmp.cleanup()
    def post(self,route,data):return self.client.post('/api/'+route,json=data,headers=self.headers)
    def test_auth_and_ui(self):
        self.assertEqual(self.client.get('/api/status').status_code,401)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/api/status',headers=self.headers).status_code,200)
    def test_demo_never_buy(self):
        data=self.post('lookup',{'card':CARD,'demo':True}).json();self.assertEqual(data['used'],0)
        res=self.post('evaluate',{'key':data['key'],'selected':[r['id'] for r in data['rows']],'settings':{'bid':1}}).json();self.assertEqual(res['recommendation'],'DEMO ONLY')
    @patch('backend.provider.fetch')
    def test_live_cache_and_refresh(self,fetch):
        fetch.return_value=[sale(i) for i in range(1,11)]+[sale(22,title='2020 Panini Prizm Anthony Edwards #258 PSA 10 Silver')]
        data=self.post('lookup',{'card':CARD}).json();self.assertEqual(len(data['rows']),10);self.assertEqual(data['origin'],'provider')
        second=self.post('lookup',{'card':CARD}).json();self.assertEqual(second['origin'],'cache');self.assertEqual(fetch.call_count,1)
        res=self.post('evaluate',{'key':data['key'],'selected':[r['id'] for r in data['rows']],'settings':{'bid':10}}).json();self.assertEqual(res['recommendation'],'BUY CANDIDATE');self.assertGreater(res['max_bid'],10)
        self.assertEqual(fetch.call_count,1)
        self.post('lookup',{'card':CARD,'refresh':True});self.assertEqual(fetch.call_count,2)
    @patch('backend.provider.fetch')
    def test_stale_fallback_and_budget(self,fetch):
        fetch.return_value=[sale(i) for i in range(1,11)]
        data=self.post('lookup',{'card':CARD}).json()
        with core.connection() as c:c.execute('UPDATE cache SET fetched=?',((core.now()-timedelta(days=2)).isoformat(),))
        with patch.dict(os.environ,{'MONTHLY_LIMIT':'1'}):
            stale=self.post('lookup',{'card':CARD}).json();self.assertTrue(stale['stale']);self.assertEqual(fetch.call_count,1)
            r=self.post('evaluate',{'key':data['key'],'selected':[x['id'] for x in data['rows']],'settings':{'bid':1}}).json();self.assertEqual(r['recommendation'],'STALE — PASS')
    def test_filter(self):
        self.assertIsNotNone(core.candidate(sale(1),CARD))
        for extra in ['Silver',' /99','lot','autograph','reprint','Gold']:
            self.assertIsNone(core.candidate(sale(1,title='2020 Panini Prizm Anthony Edwards #258 PSA 10 '+extra),CARD))
        wrong=sale(1);wrong['card']['grade']='9';self.assertIsNone(core.candidate(wrong,CARD))
    def test_bid_limit_and_low_data(self):
        rows=core.matches([sale(i) for i in range(1,11)],CARD)
        settings=Settings(bid=20).model_dump();r=core.calculate(rows,settings,core.stamp(),'compsapi');self.assertEqual(r['recommendation'],'BUY CANDIDATE')
        settings['bid']=r['max_bid']+.01;self.assertEqual(core.calculate(rows,settings,core.stamp(),'compsapi')['recommendation'],'PASS')
        self.assertEqual(core.calculate(rows[:4],settings,core.stamp(),'compsapi')['recommendation'],'INSUFFICIENT DATA')
if __name__=='__main__':unittest.main()
