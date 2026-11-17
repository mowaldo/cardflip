import base64, io, os, tempfile, unittest
from unittest.mock import patch, MagicMock
from PIL import Image
from fastapi.testclient import TestClient
from backend import vision, core
from backend.main import app, Settings
from test_app import CARD, sale

JORDAN={'p':'Jordan Love','s':'American Football','y':2020,'m':'Panini','t':'Mosaic','n':'#211','v':None,'g':'PSA','d':10,'gt':'GEM MT','r':True,'a':False,'ps':None,'c':'53353413'}
class TestVision(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32});self.env.start();self.client=TestClient(app);self.headers={'X-Local-Token':'a'*32}
        b=io.BytesIO();Image.new('RGB',(100,150),'white').save(b,'PNG');self.img=b.getvalue()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_normalize(self):
        r=vision.normalize(JORDAN);self.assertEqual(r['fields'],{'player':'Jordan Love','year':'2020','set':'Panini Mosaic','number':'211','grader':'PSA','grade':'10'});self.assertEqual(r['missing'],['variant']);self.assertFalse(r['auto_eligible']);self.assertEqual(r['metadata']['cert_number'],'53353413')
    def test_complete(self):
        r=vision.normalize(dict(JORDAN,v='Silver'));self.assertTrue(r['auto_eligible']);self.assertEqual(r['fields']['variant'],'Silver')
        for change in ({'ps':'15/99'},{'a':True},{'n':'53353413'},{'v':'Rookie'},{'v':'None'}):self.assertFalse(vision.normalize(dict(JORDAN,v='Silver',**{k:v for k,v in change.items() if k!='v'}) if 'v' not in change else dict(JORDAN,v=change['v']))['auto_eligible'])
    def test_designation(self):
        r=vision.normalize(dict(JORDAN,p='Cooper Flagg',m='Topps',t='Topps Now',g='CGC',gt='Pristine',y='2025-26',n='241',v='Base'))
        self.assertEqual(r['fields']['grade_type'],'Pristine');self.assertEqual(r['fields']['set'],'Topps Now');self.assertEqual(r['fields']['year'],'2025');self.assertTrue(r['auto_eligible'])
        self.assertFalse(vision.normalize(dict(JORDAN,g='CGC',gt=None,v='Base'))['auto_eligible'])
    def test_raw_no_graded_pricing(self):
        r=vision.normalize(dict(JORDAN,g='RAW',d=None,gt=None,c=None,v='Base'));self.assertTrue(r['auto_eligible']);self.assertEqual(r['fields']['grader'],'RAW');self.assertNotIn('grade',r['fields']);self.assertEqual(r['metadata']['grader'],'RAW')
    @patch('backend.vision.session')
    def test_endpoint_cache_and_no_quota(self,session):
        import json
        s=session.return_value.__enter__.return_value
        s.post.return_value.json.return_value={'message':{'content':json.dumps(JORDAN)},'done_reason':'stop','eval_count':91}
        body={'image':base64.b64encode(self.img).decode(),'mode':'fast'}
        r=self.client.post('/api/vision',json=body,headers=self.headers);self.assertEqual(r.status_code,200);self.assertFalse(r.json()['cached']);self.assertEqual(r.json()['fields']['player'],'Jordan Love')
        self.assertFalse(s.post.call_args.kwargs['json']['think']);self.assertEqual(s.post.call_args.args[0],'http://127.0.0.1:11434/api/chat')
        r=self.client.post('/api/vision',json=body,headers=self.headers);self.assertTrue(r.json()['cached']);self.assertEqual(s.post.call_count,1);self.assertEqual(core.used(),0)
        self.assertEqual(self.client.post('/api/vision',json=body).status_code,401)
    def test_more_than_ten_sales(self):
        rows=core.matches([sale(i) for i in range(1,25)],CARD);r=core.calculate(rows,Settings(bid=20).model_dump(),core.stamp(),'compsapi');self.assertEqual(r['count'],24);self.assertGreater(r['break_even_bid'],r['max_bid'])
if __name__=='__main__':unittest.main()
