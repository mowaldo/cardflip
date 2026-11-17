import base64, os, tempfile, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app
from backend import core, reference_market, provider
from test_visual_library import CARD, photo


def listing(i,variant='Base',number='211',player='Jordan Love',image='https://i.ebayimg.com/images/g/test/s-l500.jpg'):
    return {'item_id':str(i),'title':f'2020 Panini Mosaic {player} #{number} {variant} PSA 10','image':image,'price':99999,'url':'https://example.com/bad'}

class MarketReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32,'COMPSAPI_KEY':'fake','MONTHLY_LIMIT':'100'});self.env.start();self.client=TestClient(app);self.h={'X-Local-Token':'a'*32};self.body={'card':CARD,'image':photo(),'confirmed':True}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def post(self,body=None):return self.client.post('/api/reference/market',json=self.body if body is None else body,headers=self.h)
    def test_candidate_filters(self):
        rows=reference_market.candidates([listing(1),listing(1),listing(2,'Silver Prizm'),listing(3,number='999'),listing(4,player='Another Player'),listing(5,image='https://evil.example/images/x'),listing(6,'autograph'),listing(7,'')],CARD)
        self.assertEqual([r['id'] for r in rows],['1','2','7']);self.assertNotIn('price',rows[0]);self.assertEqual(rows[0]['url'],'https://www.ebay.com/itm/1');self.assertEqual(rows[-1]['variant'],'Unspecified')
    def test_url_allowlist(self):
        for url in ['http://i.ebayimg.com/images/x','https://i.ebayimg.com.evil.com/images/x','https://i.ebayimg.com:444/images/x','https://a@i.ebayimg.com/images/x','https://i.ebayimg.com/other/x','https://127.0.0.1/images/x']:
            self.assertIsNone(reference_market.image_url(url))
    @patch('backend.reference_market.download')
    @patch('backend.provider.fetch_active')
    def test_rank_cache_quota_no_prices(self,fetch,download):
        fetch.return_value=[listing(1),listing(2,'Silver Prizm')];download.return_value=base64.b64decode(photo());r=self.post();self.assertEqual(r.status_code,200);d=r.json();self.assertEqual(d['count'],2);self.assertFalse(d['verified']);self.assertEqual(d['origin'],'provider');self.assertEqual(core.used(),1);self.assertNotIn('price',d['matches'][0]);self.assertEqual(self.post().json()['origin'],'cache');self.assertEqual(fetch.call_count,1);self.assertEqual(core.used(),1)
        with core.connection() as c:self.assertFalse(c.execute("SELECT name FROM sqlite_master WHERE name='visual_refs'").fetchone())
    @patch('backend.provider.fetch_active')
    def test_guardrails(self,fetch):
        self.assertEqual(self.post(dict(self.body,confirmed=False)).status_code,422);self.assertEqual(self.post(dict(self.body,card=dict(CARD,number=''))).status_code,422);self.assertEqual(self.post(dict(self.body,image='invalid')).status_code,400);self.assertEqual(self.client.post('/api/reference/market',json=self.body).status_code,401)
        with patch.dict(os.environ,{'MONTHLY_LIMIT':'0'}):self.assertEqual(self.post().status_code,503)
        fetch.assert_not_called();self.assertEqual(core.used(),0)
    @patch('backend.provider.requests.get')
    def test_provider_contract(self,get):
        get.return_value.status_code=200;get.return_value.json.return_value={'ok':True,'items':[listing(1)]};self.assertEqual(len(provider.fetch_active(CARD)),1);self.assertEqual(get.call_args.args[0],'https://api.compsapi.com/v1/active');self.assertEqual(get.call_args.kwargs['params']['per_page'],100);self.assertFalse(get.call_args.kwargs['allow_redirects'])
    @patch('backend.reference_market.requests.get')
    def test_download_no_redirects_no_key(self,get):
        r=get.return_value.__enter__.return_value;r.status_code=302;self.assertIsNone(reference_market.download(listing(1)['image']));self.assertFalse(get.call_args.kwargs['allow_redirects']);self.assertNotIn('X-API-Key',get.call_args.kwargs['headers'])
