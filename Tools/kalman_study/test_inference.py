import unittest
from infer_robust import infer


def records(ratios):
    out=[]
    for seed,ratio in enumerate(ratios):
        for prefix in ['C1','C4','C5']:
            for arm,value in [('off',10.),('on',10.*ratio)]:
                out.append(dict(seed=seed,case=prefix+'_fixture',arm=arm,rmse_m=value,broken_pct=20. if arm=='off' else 10.))
    return out


class InferenceTests(unittest.TestCase):
    def test_all_six_paired_gains(self):
        r=infer(records([.5]*6),['C1','C4','C5'],list(range(6)),1000)
        self.assertAlmostEqual(r['geometric_rmse_reduction_pct'],50.)
        self.assertEqual(r['exact_two_sided_sign_flip_p'],2/64)
        self.assertTrue(r['meets_predeclared_practical_target'])

    def test_no_difference(self):
        r=infer(records([1.]*6),['C1','C4','C5'],list(range(6)),1000)
        self.assertEqual(r['exact_two_sided_sign_flip_p'],1.)
        self.assertFalse(r['passes_two_sided_005'])

    def test_incomplete_block_is_not_silently_dropped(self):
        with self.assertRaises(ValueError):infer(records([.5]*5),['C1','C4','C5'],list(range(6)),1000)

if __name__=='__main__':unittest.main()
