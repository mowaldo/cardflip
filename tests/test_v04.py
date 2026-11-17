import unittest
from unittest.mock import patch
from backend import recognition, core
import test_app
from test_app import sale

CGC={'year':'2025','player':'Cooper Flagg','set':'Topps Now','number':'241','variant':'Base','grader':'CGC','grade':'10','grade_type':'Pristine'}
def cgc_sale(i,title):
    x=sale(i,title=title);x['card']={'grader':'CGC','grade':'10','card_number':'241'};return x
class MultiGraderTests(unittest.TestCase):
    def test_cgc(self):
        r=recognition.parse_label('2025-26 Topps Now\n#241 Cooper Flagg |\nCGC PRISTINE 10')
        self.assertEqual(r['fields'],{k:v for k,v in CGC.items() if k!='variant'})
        self.assertEqual(r['missing'],['variant'])
    def test_other_grader_text(self):
        for grader,grade in [('BGS','9.5 GEM MINT'),('SGC','10 GEM MINT')]:
            r=recognition.parse_label(f'2020 PANINI PRIZM #258\nANTHONY EDWARDS\n{grader}\n{grade}')
            self.assertEqual(r['fields']['grader'],grader)
            self.assertEqual(r['fields']['player'],'Anthony Edwards')
            self.assertEqual(r['fields']['grade'],grade.split()[0])
    def test_cgc_unknown_designation(self):
        r=recognition.parse_label('2025 Topps Now\n#241 Cooper Flagg\nCGC 10')
        self.assertIn('grade_type',r['missing'])
    def test_grade_filter(self):
        prefix='2025-26 Topps Now Cooper Flagg #241 CGC '
        rows=core.matches([cgc_sale(1,prefix+'Pristine 10 Gold Label'),cgc_sale(2,prefix+'Gem Mint 10'),cgc_sale(3,prefix+'10'),cgc_sale(4,prefix+'Pristine 10 Gold Refractor')],CGC)
        self.assertEqual([r['id'] for r in rows],['1'])
    def test_grade_cache_key(self):
        self.assertNotEqual(core.cache_key(CGC),core.cache_key(dict(CGC,grade_type='Gem Mint')))
class GradeApiTests(unittest.TestCase):
    setUp=test_app.TestApp.setUp;tearDown=test_app.TestApp.tearDown;post=test_app.TestApp.post
    def test_missing_type(self):
        r=self.post('lookup',{'card':dict(CGC,grade_type='')})
        self.assertEqual(r.status_code,422)
        self.assertEqual(self.client.get('/api/status',headers=self.headers).json()['used'],0)
    @patch('backend.provider.fetch')
    def test_cgc_lookup_cache(self,fetch):
        fetch.return_value=[cgc_sale(1,'2025 Topps Now Cooper Flagg #241 CGC Pristine 10')]
        a=self.post('lookup',{'card':CGC});self.assertEqual(a.status_code,200)
        b=self.post('lookup',{'card':CGC});self.assertEqual(b.json()['origin'],'cache')
        self.assertEqual(fetch.call_count,1)
        c=self.post('lookup',{'card':dict(CGC,grade_type='Gem Mint')});self.assertEqual(c.status_code,200);self.assertEqual(c.json()['rows'],[])
