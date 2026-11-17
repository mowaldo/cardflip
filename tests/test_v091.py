import base64,io,json,os,tempfile,unittest
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from backend import core,variants
from backend.main import app
from test_v09 import CARD,sale
class TestV091(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32});self.env.start();self.client=TestClient(app);self.h={'X-Local-Token':'a'*32}
        b=io.BytesIO();Image.new('RGB',(100,150),'white').save(b,'PNG');self.img=base64.b64encode(b.getvalue()).decode()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    @patch('backend.vision.session')
    def test_visual_compare(self,session):
        s=session.return_value.__enter__.return_value;s.post.return_value.json.return_value={'message':{'content':json.dumps({'result':'uncertain','evidence':'Glare obscures foil pattern.'})},'done_reason':'stop'}
        body={'image':self.img,'reference':self.img,'variant':'Silver'}
        r=self.client.post('/api/visual-compare',json=body,headers=self.h);self.assertEqual(r.status_code,200);self.assertEqual(r.json()['result'],'uncertain');self.assertFalse(r.json()['verified']);self.assertEqual(core.used(),0);self.assertEqual(len(s.post.call_args.kwargs['json']['messages'][0]['images']),2);self.assertEqual(self.client.post('/api/visual-compare',json=body).status_code,401)
        self.assertEqual(self.client.post('/api/visual-compare',json=dict(body,reference='a'),headers=self.h).status_code,400)
    @patch('backend.vision.session')
    def test_invalid_visual_response(self,session):
        s=session.return_value.__enter__.return_value;s.post.return_value.json.return_value={'message':{'content':'{"result":"verified","evidence":"yes"}'}}
        self.assertEqual(self.client.post('/api/visual-compare',json={'image':self.img,'reference':self.img},headers=self.h).status_code,422)
    def test_aliases(self):
        self.assertEqual(variants.group_name(sale(1,variant='Prizm Silver'),CARD),'Silver Prizm');self.assertEqual(variants.group_name(sale(2,variant='Silver Mosaic'),CARD),'Silver Mosaic');self.assertEqual(variants.group_name(sale(3,variant='Camo Pink'),CARD),'Pink Camo')
