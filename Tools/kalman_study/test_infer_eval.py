import math
import unittest
from infer_eval import block_test


def records(effects, cases=('C8', 'C10')):
    out = []
    for seed, effect in effects.items():
        for case in cases:
            out.append(dict(case=case+'_x', seed=seed, arm='off', rmse_m=10.0, broken_pct=20.0))
            out.append(dict(case=case+'_x', seed=seed, arm='on_ego', rmse_m=10.0*math.exp(effect), broken_pct=10.0))
    return out


class InferEvalTest(unittest.TestCase):
    def test_all_blocks_favoring_gives_minimum_exact_p(self):
        seeds = list(range(8))
        r = block_test(records({s: -0.3 for s in seeds}), 'on_ego', 'off', ['C8', 'C10'], seeds)
        self.assertAlmostEqual(r['exact_two_sided_sign_flip_p'], 2/256)
        self.assertAlmostEqual(r['geometric_rmse_reduction_pct'], 100*(1-math.exp(-0.3)), places=6)
        self.assertTrue(r['meets_practical_target'])

    def test_mixed_signs_not_significant(self):
        seeds = list(range(6))
        r = block_test(records({s: (-0.2 if s % 2 else 0.2) for s in seeds}), 'on_ego', 'off', ['C8', 'C10'], seeds)
        self.assertEqual(r['exact_two_sided_sign_flip_p'], 1.0)
        self.assertEqual(r['blocks_favoring_treatment'], 3)

    def test_incomplete_block_refused(self):
        data = records({1: -0.1, 2: -0.1})[:-1]
        with self.assertRaises(ValueError):
            block_test(data, 'on_ego', 'off', ['C8', 'C10'], [1, 2])


if __name__ == '__main__':
    unittest.main()
