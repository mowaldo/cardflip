import base64,io,os,tempfile,unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from backend.main import app
from backend import visual_library,core
import numpy as np
import cv2

CARD={'player':'Jordan Love','year':'2020','set':'Panini Mosaic','number':'211'}

def photo(color='red'):
    im=Image.new('RGB',(500,640),'#252525');d=ImageDraw.Draw(im)
    d.rectangle((90,65,410,575),fill=color,outline='white',width=4)
    for i in range(10):d.rectangle((105+i*7,90+i*9,390-i*5,550-i*12),outline='black',width=2)
    d.text((150,310),'JORDAN LOVE #211',fill='white');b=io.BytesIO();im.save(b,'PNG');return base64.b64encode(b.getvalue()).decode()

class VisualTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32});self.env.start();self.client=TestClient(app);self.h={'X-Local-Token':'a'*32}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def post(self,path,body):return self.client.post('/api/reference/'+path,json=body,headers=self.h)
    def save(self,variant='Base',image=None,card=CARD):return self.post('save',{'card':card,'image':image or photo(),'variant':variant,'confirmed':True})
    def test_save_duplicate_delete(self):
        r=self.save();self.assertEqual(r.status_code,200);rid=r.json()['id'];self.assertFalse(r.json()['duplicate']);self.assertTrue(self.save().json()['duplicate']);self.assertTrue(self.post('delete',{'id':rid}).json()['deleted']);self.assertFalse(self.post('delete',{'id':rid}).json()['deleted'])
    def test_rank_separation_and_no_api(self):
        self.save('Red',photo('red'));self.save('Blue',photo('blue'));self.save('Other card',photo(),dict(CARD,number='999'));self.save('Other family',photo(),dict(CARD,player='Other Player'))
        r=self.post('rank',{'card':CARD,'image':photo()});self.assertEqual(r.status_code,200);result=r.json();self.assertEqual(result['count'],2);self.assertEqual(result['matches'][0]['variant'],'Red');self.assertFalse(result['verified']);self.assertEqual(core.used(),0);self.assertTrue(result['matches'][0]['thumbnail']);self.assertGreaterEqual(result['matches'][0]['score'],result['matches'][1]['score']);self.assertEqual(self.post('rank',{'card':dict(CARD,player='No Player'),'image':photo()}).json()['count'],0)
    def test_guardrails(self):
        self.assertEqual(self.save('Unknown').status_code,422);self.assertEqual(self.save(card=dict(CARD,number='')).status_code,422);self.assertEqual(self.save(image='invalid').status_code,400);self.assertEqual(self.client.post('/api/reference/save',json={'card':CARD,'image':photo(),'variant':'Base','confirmed':True}).status_code,401);self.assertEqual(self.post('save',{'card':CARD,'image':photo(),'variant':'Base','confirmed':False}).status_code,422)
    def test_crop(self):
        im=visual_library.read_image(base64.b64decode(photo()));crop,detected=visual_library.isolate(im);self.assertTrue(detected);self.assertLess(crop.shape[0]*crop.shape[1],im.shape[0]*im.shape[1]);flat=np.zeros((200,200,3),np.uint8);self.assertFalse(visual_library.isolate(flat)[1])
