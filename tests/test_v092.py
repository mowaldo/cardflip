import unittest
from datetime import timedelta
from backend import board,core
from backend.main import Settings
from test_v09 import CARD,sale

class TestReferenceBid(unittest.TestCase):
    def cell(self,items,variant='Base',fetched=None):
        result=board.build(items,CARD,Settings().model_dump(),fetched or core.now().isoformat())
        return next(g['cells']['PSA 10'] for g in result['groups'] if g['variant']==variant)
    def test_sparse_reference_only(self):
        c=self.cell([sale(1,price=45)])
        self.assertIsNone(c['max_bid']);self.assertGreater(c['reference_bid'],0);self.assertGreaterEqual(c['reference_profit'],5);self.assertGreaterEqual(c['reference_roi'],25)
    def test_stale_and_unspecified(self):
        self.assertIsNone(self.cell([sale(1)],fetched=(core.now()-timedelta(days=2)).isoformat())['reference_bid'])
        c=self.cell([sale(i,variant='') for i in range(1,7)],'Unspecified');self.assertIsNone(c['max_bid']);self.assertIsNone(c['reference_bid'])
    def test_unknown_shipping_conservative(self):
        a=self.cell([sale(1,price=45,shipping=None)]);b=self.cell([sale(1,price=45,shipping=5)])
        self.assertLess(a['reference_bid'],b['reference_bid']);self.assertIsNone(a['max_bid'])
    def test_no_margin_pass(self):
        c=self.cell([sale(1,price=2,shipping=0)]);self.assertEqual(c['reference_bid'],0);self.assertIsNone(c['reference_profit'])
