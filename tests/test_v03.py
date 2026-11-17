import io
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from PIL import Image
from backend import label_image, recognition

class LabelImageTests(unittest.TestCase):
    def fixture(self):
        im=np.full((500,400,3),220,dtype=np.uint8)
        cv2.rectangle(im,(70,40),(330,105),(0,0,180),4)
        return im
    def test_locates_label(self):
        x,y,w,h=label_image.label_box(self.fixture())
        self.assertTrue(60<x<80 and 30<y<50 and 250<w<275 and 60<h<75)
    @patch('backend.label_image._read',side_effect=['2020 PANINI MOSAIC\nJORDAN LOVE','#211\nGEM MT\n10'])
    def test_separate_columns(self,read):
        stream=io.BytesIO();Image.fromarray(cv2.cvtColor(self.fixture(),cv2.COLOR_BGR2RGB)).save(stream,format='PNG')
        r=label_image.scan_label(stream.getvalue())
        self.assertEqual(r['fields'],{'year':'2020','number':'211','set':'Panini Mosaic','grader':'PSA','grade':'10','player':'Jordan Love'})
        self.assertEqual(r['missing'],['variant']);self.assertEqual(read.call_count,2)
    @patch('backend.label_image._read')
    def test_does_not_scan_artwork(self,read):
        stream=io.BytesIO();Image.new('RGB',(300,450),'gray').save(stream,format='PNG')
        r=label_image.scan_label(stream.getvalue());self.assertFalse(r['fields']);read.assert_not_called()
    def test_rejects_unanchored_player(self):
        r=recognition.parse_label('#211\nG3\nMr Ad');self.assertNotIn('player',r['fields'])

    def test_actual_noisy_label(self):
        r=recognition.parse_label('— SS a\n2020 PANINI MOSAIC\nJORDAN LOVE\nSeetieinet ie\n#211\nGEM MT\n10')
        self.assertEqual(r['fields']['player'],'Jordan Love')
        self.assertEqual(r['missing'],['variant'])
    def test_two_plausible_names_stay_ambiguous(self):
        for other in ('AARON RODGERS','Aaron Rodgers'):
            r=recognition.parse_label('2020 PANINI MOSAIC\nJORDAN LOVE\n'+other+'\n#211\nGEM MT\n10')
            self.assertNotIn('player',r['fields'])
    @patch('backend.label_image._read',side_effect=['— SS a\n2020 PANINI MOSAIC\nJORDAN LOVE\nSeetieinet ie','#211\nGEM MT\n10'])
    def test_noisy_columns(self,read):
        stream=io.BytesIO();Image.fromarray(cv2.cvtColor(self.fixture(),cv2.COLOR_BGR2RGB)).save(stream,format='PNG')
        r=label_image.scan_label(stream.getvalue())
        self.assertEqual(r['fields']['player'],'Jordan Love');self.assertEqual(r['missing'],['variant'])
