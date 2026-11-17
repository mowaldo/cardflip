import unittest, tempfile, os
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import core, provider, vision
from backend.main import app, Settings
from test_app import CARD, sale
from test_v05 import JORDAN

RAW={'year':'2024','player':'Ricky Pearsall','set':'Topps Chrome Black','number':'','variant':'Autograph Insert','grader':'RAW','grade':'','print_run':'75'}
def raw_sale(i,extra='',run='75',grade=False):
    x=sale(i,35,title=f'2024 Topps Chrome Black Ricky Pearsall Auto {i}/{run} {extra}');x['card']={'graded':grade,'grader':'PSA' if grade else None,'grade':'10' if grade else None};return x
class TestRaw(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.env=patch.dict(os.environ,{'CARDFLIP_DB':self.tmp.name+'/test.db','LOCAL_TOKEN':'a'*32,'COMPSAPI_KEY':'fake-key','MONTHLY_LIMIT':'100'});self.env.start();self.client=TestClient(app);self.h={'X-Local-Token':'a'*32}
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def post(self,path,data):return self.client.post('/api/'+path,json=data,headers=self.h)
    def test_raw_serial_normalization(self):
        r=vision.normalize(dict(JORDAN,p='Ricky Pearsall',y='2024',m='Topps',t='Chrome Black',n='73/75',g='RAW',d=None,gt=None,c=None,v='Autograph Insert',a=True,ps=None));self.assertNotIn('number',r['fields']);self.assertEqual(r['fields']['print_run'],'75');self.assertEqual(r['metadata']['print_serial'],'73/75');self.assertTrue(r['auto_eligible'])
    def test_raw_candidates(self):
        self.assertIsNotNone(core.candidate(raw_sale(1),RAW))
        for x in (raw_sale(2,run='99'),raw_sale(3,grade=True),raw_sale(4,'PSA 10'),raw_sale(5,'Gold'),raw_sale(6,'Patch'),raw_sale(7,'lot')):self.assertIsNone(core.candidate(x,RAW))
        self.assertIsNone(core.candidate(raw_sale(8),dict(RAW,print_run='')))
    @patch('backend.provider.requests.get')
    def test_raw_params(self,get):
        get.return_value.status_code=200;get.return_value.json.return_value={'items':[]};provider.fetch(RAW);p=get.call_args.kwargs['params'];self.assertEqual(p['graded'],'false');self.assertNotIn('grader',p);self.assertNotIn('grade',p);self.assertNotIn('RAW',p['q']);self.assertNotIn('73/75',p['q'])
    @patch('backend.provider.fetch')
    def test_raw_lookup_no_number_conditional(self,fetch):
        fetch.return_value=[raw_sale(i) for i in range(1,8)];r=self.post('lookup',{'card':RAW});self.assertEqual(r.status_code,200,r.text);data=r.json();self.assertEqual(len(data['rows']),7)
        for preview in (True,False):
            result=self.post('evaluate',{'key':data['key'],'selected':[x['id'] for x in data['rows']],'settings':{},'preview':preview}).json();self.assertEqual(result['recommendation'],'REVIEW — PASS');self.assertGreater(result['max_bid'],0);self.assertGreaterEqual(result['profit_at_max'],5)
        self.assertEqual(self.post('lookup',{'card':RAW}).json()['origin'],'cache');self.assertEqual(fetch.call_count,1)
    def test_require_raw_grade_blank(self):
        self.assertEqual(self.post('lookup',{'card':dict(RAW,grade='10')}).status_code,422);self.assertEqual(self.post('lookup',{'card':dict(RAW,print_run='')}).status_code,422)
    def test_max_independent_of_bid(self):
        rows=core.matches([sale(i) for i in range(1,11)],CARD);a=core.calculate(rows,Settings().model_dump(),core.stamp(),'compsapi');b=core.calculate(rows,Settings(bid=20).model_dump(),core.stamp(),'compsapi');self.assertEqual(a['max_bid'],b['max_bid']);self.assertEqual(a['profit_at_max'],b['profit_at_max']);self.assertGreaterEqual(a['roi_at_max'],25)
