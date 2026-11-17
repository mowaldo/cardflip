import base64,unittest
from unittest.mock import patch
import numpy as np
from backend import embeddings,visual_library,reference_market
from test_visual_library import CARD,photo
from test_reference_market import listing

class EmbeddingTests(unittest.TestCase):
    @patch('backend.embeddings.installed',return_value=False)
    def test_missing_weights_no_load(self,installed):
        with patch('backend.embeddings._load') as load:
            self.assertIsNone(embeddings.vectors([np.zeros((100,100,3),dtype=np.uint8)]));load.assert_not_called()
    @patch('backend.embeddings.installed',return_value=True)
    @patch('backend.embeddings._load',side_effect=ImportError('missing'))
    def test_fallback(self,load,installed):
        rows=[{'score':.5}];self.assertEqual(embeddings.rerank(None,[None],rows),'OpenCV');self.assertEqual(rows,[{'score':.5}])
    @patch('backend.embeddings.vectors',return_value=np.array([[1.,0.],[1.,0.],[0.,1.]]))
    def test_fusion(self,vecs):
        rows=[{'score':.5},{'score':.5}];self.assertEqual(embeddings.rerank(None,[None,None],rows),'OpenCV + DINOv2');self.assertEqual(rows[0]['score'],.625);self.assertEqual(rows[1]['score'],.375);self.assertEqual(rows[0]['opencv_score'],.5);self.assertEqual(rows[0]['embedding_similarity'],1.)
    @patch('backend.embeddings.vectors',return_value=np.array([[1.,0.],[1.,0.]]))
    @patch('backend.reference_market.download')
    def test_market_integration(self,download,vecs):
        data=base64.b64decode(photo());download.return_value=data
        result=reference_market.rank(CARD,data,[listing(1)])
        self.assertEqual(result['engine'],'OpenCV + DINOv2');self.assertEqual(result['matches'][0]['embedding_similarity'],1.);self.assertFalse(result['verified']);self.assertNotIn('price',result['matches'][0])
