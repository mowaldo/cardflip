import os, tempfile, unittest
from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import board, core, provider
from backend.main import app, Settings

CARD={'player':'Jordan Love','year':'2020','set':'Panini Mosaic','number':'211'}
def sale(i,grade='10',variant='Base',number='211',price=45,shipping=2,age=None):
    grader='PSA' if grade else None
    return {'item_id':str(i),'title':f'2020 Panini Mosaic Jordan Love #{number} {variant} '+(f'PSA {grade}' if grade else ''),'price':price,'shipping_cost':shipping,'last_sold':(core.now()-timedelta(days=age if age is not None else i%15+1)).isoformat(),'card':{'grader':grader,'grade':grade,'graded':bool(grade),'card_number':number},'url':'https://www.ebay.com/itm/123'}
class TestBoard(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32,'COMPSAPI_KEY':'fake','MONTHLY_LIMIT':'100'});self.env.start();self.client=TestClient(app);self.h={'X-Local-Token':'a'*32}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def post(self,card=CARD,**kwargs):return self.client.post('/api/board',json={'card':card,**kwargs},headers=self.h)
    def test_mixed_prices_and_no_cross_grade(self):
        items=[sale(i,'10','Base',price=50) for i in range(1,7)]+[sale(i,'9','Base',price=25) for i in range(10,16)]+[sale(i,None,'Silver',price=40) for i in range(20,26)]+[sale(30,'10','Genesis',price=500),sale(31,'10','',price=200),sale(32,'10','Base','999',price=2000)]
        with patch('backend.provider.fetch_board',return_value=items) as f:
            out=self.post().json();g={x['variant']:x['cells'] for x in out['groups']};self.assertEqual(g['Base']['PSA 10']['median'],52);self.assertEqual(g['Base']['PSA 9']['median'],27);self.assertEqual(g['Silver']['Raw']['median'],42);self.assertIsNone(g['Genesis']['PSA 10']['max_bid']);self.assertEqual(g['Genesis']['PSA 10']['median'],502);self.assertEqual(g['Unspecified']['PSA 10']['count'],1);self.assertGreater(g['Base']['PSA 10']['max_bid'],0);self.assertEqual(out['used'],1)
            self.assertEqual(self.post(settings={'min_profit':20}).json()['origin'],'cache');self.assertEqual(f.call_count,1)
            exact=self.client.post('/api/lookup',json={'card':dict(CARD,variant='Base',grader='PSA',grade='10')},headers=self.h).json();self.assertEqual(exact['origin'],'price board cache');self.assertEqual(core.used(),1)
    def test_unknown_number_separates_families_and_loose(self):
        items=[sale(1,'10','Base','211'),sale(2,'10','Base','222')];x=sale(3,None,'Base');x['title']='2020 Panini Mosaic Jordan Love Base';x['card']['card_number']='';items.append(x)
        with patch('backend.provider.fetch_board',return_value=items):
            r=self.post(dict(CARD,number='RC')).json();self.assertEqual({x['number'] for x in r['groups']},{'211','222'});self.assertEqual(r['unresolved_count'],1)
    def test_specials_unknown_shipping_stale_and_conflict(self):
        items=[sale(i,price=60,shipping=None) for i in range(1,7)];special=sale(7,None,'Autograph /75');items.append(special);conflict=sale(8,'10');conflict['title']=conflict['title'].replace('PSA 10','PSA 9');items.append(conflict)
        with patch('backend.provider.fetch_board',return_value=items):
            r=self.post().json();self.assertIsNone(r['groups'][0]['cells']['PSA 10']['max_bid']);self.assertEqual(r['groups'][0]['cells']['PSA 10']['item_median'],60);self.assertEqual(r['unresolved_count'],1);self.assertEqual(r['matched_count'],7)
        with core.connection() as c:c.execute('UPDATE cache SET fetched=?',((core.now()-timedelta(days=2)).isoformat(),))
        with patch.dict(os.environ,{'MONTHLY_LIMIT':'1'}):self.assertTrue(self.post().json()['stale'])
    @patch('backend.provider.requests.get')
    def test_provider_mixed(self,get):
        get.return_value.status_code=200;get.return_value.json.return_value={'items':[]};provider.fetch_board(CARD);p=get.call_args.kwargs['params'];self.assertEqual(p['size'],240);self.assertNotIn('graded',p);self.assertNotIn('grade',p);self.assertNotIn('grader',p);self.assertNotIn('PSA',p['q'])
    def test_player_only_no_group(self):
        with patch('backend.provider.fetch_board',return_value=[sale(1)]):
            r=self.post({'player':'Jordan Love'}).json();self.assertEqual(r['groups'],[]);self.assertEqual(r['unresolved_count'],1)
