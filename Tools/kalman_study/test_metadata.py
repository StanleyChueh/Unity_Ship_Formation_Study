"""Regression for the frozen harness's documented ID-box y-origin correction."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from analyze import load


class MetadataTests(unittest.TestCase):
    def fixture(self,path,y):
        (path/'unity.complete').write_text('complete');(path/'bridge.complete').write_text('complete')
        rows=[dict(step=i,t=round(-5+i*.1,1),width=1280,height=720,
                   left_boxes=[dict(id=1,x=0,y=y,w=10,h=10,pixels=100)],right_boxes=[]) for i in range(651)]
        p=path/'steps.jsonl';p.write_text(''.join(json.dumps(r)+'\n' for r in rows));return p

    def test_frozen_origin_is_corrected_without_rewriting_raw(self):
        with tempfile.TemporaryDirectory(prefix='kalman-metadata-test-') as d:
            path=Path(d);p=self.fixture(path,-360);before=hashlib.sha256(p.read_bytes()).hexdigest()
            rows=load(dict(output=str(path)))
            self.assertEqual(rows[0]['left_boxes'][0]['y'],0)
            self.assertEqual(rows[0]['left_boxes'][0]['_raw_y'],-360)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),before)

    def test_future_corrected_origin_is_not_shifted_again(self):
        with tempfile.TemporaryDirectory(prefix='kalman-metadata-test-') as d:
            path=Path(d);self.fixture(path,0)
            rows=load(dict(output=str(path),id_box_encoded_y_origin=719))
            self.assertEqual(rows[0]['left_boxes'][0]['y'],0)
            self.assertEqual(rows[0]['_id_box_y_shift_px'],0)

if __name__=='__main__':unittest.main()
