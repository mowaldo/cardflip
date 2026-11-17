import base64, io, shutil, unittest
from unittest.mock import patch
from backend import recognition
import test_app
from test_app import CARD, sale

class RecognitionTests(unittest.TestCase):
    def test_base_never_guessed(self):
        r=recognition.parse_label('2020 PANINI PRIZM #258\nANTHONY EDWARDS\nPSA GEM MT 10\n123456789')
        self.assertEqual(r['fields'],{k:v for k,v in CARD.items() if k!='variant'})
        self.assertEqual(r['missing'],['variant'])
    def test_explicit_parallel(self):
        r=recognition.parse_label('2020 PANINI PRIZM #258\nANTHONY EDWARDS\nSILVER\nGEM MT 10')
        self.assertEqual(r['fields']['variant'],'Silver')
        self.assertEqual(r['missing'],[])
    def test_uncertain_identity(self):
        r=recognition.parse_label('2020 PANINI PRIZM #258\nANTHONY EDWARDS\nSILVER\nGOLD\nPSA 9\nPSA 10')
        self.assertIn('variant',r['missing']);self.assertIn('grade',r['missing'])
    def test_numbered_card_not_base(self):
        r=recognition.parse_label('2020 PANINI PRIZM #258\nANTHONY EDWARDS\nBASE\nPSA 10\n12/99')
        self.assertIn('variant',r['missing'])

class PreviewTests(unittest.TestCase):
    setUp=test_app.TestApp.setUp
    tearDown=test_app.TestApp.tearDown
    post=test_app.TestApp.post
    @patch('backend.provider.fetch')
    def test_preview_cannot_buy(self,fetch):
        fetch.return_value=[sale(i) for i in range(1,11)]
        r=self.post('lookup',{'card':CARD}).json()
        data={'key':r['key'],'selected':[],'settings':{'bid':1},'preview':True}
        p=self.post('evaluate',data).json();self.assertEqual(p['recommendation'],'PREVIEW — UNVERIFIED');self.assertGreater(p['max_bid'],0)
        data.update(preview=False,selected=[x['id'] for x in r['rows']]);self.assertEqual(self.post('evaluate',data).json()['recommendation'],'BUY CANDIDATE')
        self.assertEqual(fetch.call_count,1)
    def test_parse_api_no_request(self):
        r=self.post('parse-label',{'text':'2020 PANINI PRIZM #258\nANTHONY EDWARDS\nPSA GEM MT 10'}).json();self.assertEqual(r['fields']['player'],'Anthony Edwards')
        self.assertEqual(self.client.get('/api/status',headers=self.headers).json()['used'],0)
    def test_preview_demo(self):
        r=self.post('lookup',{'card':CARD,'demo':True}).json();p=self.post('evaluate',{'key':r['key'],'selected':[],'settings':{'bid':1},'preview':True}).json();self.assertEqual(p['recommendation'],'DEMO ONLY')
