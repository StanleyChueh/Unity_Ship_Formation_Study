#!/usr/bin/env python3
"""Held-out inference per the frozen protocol: seed blocks, exact sign-flip test.

For each hypothesis (treatment arm vs baseline arm) and each held-out seed, the
block statistic is the mean over the primary-family cases of
log(RMSE_treatment / RMSE_baseline). The exact two-sided paired sign-flip test
enumerates all 2^n sign patterns. Hypotheses are tested in the protocol's fixed
sequence at alpha (gatekeeping: stop at the first non-rejection), which controls
the family-wise error rate without splitting alpha. Frames and followers are not
treated as replicates. Bootstrap intervals resample whole seed blocks.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np


def block_test(records, treatment, baseline, cases, seeds, draws=20000):
    blocks, detail = [], []
    for seed in seeds:
        ratios, broken = [], []
        for case in cases:
            pair = {r['arm']: r for r in records if r['case'].split('_')[0] == case and r['seed'] == seed}
            if treatment not in pair or baseline not in pair:
                raise ValueError(f'Incomplete primary block {seed}/{case}: refusing partial inference')
            ratios.append(float(np.log(pair[treatment]['rmse_m']/pair[baseline]['rmse_m'])))
            broken.append(pair[baseline]['broken_pct']-pair[treatment]['broken_pct'])
        blocks.append(float(np.mean(ratios)))
        detail.append(dict(seed=seed, case_log_rmse_ratios=dict(zip(cases, ratios)), mean_log_rmse_ratio=blocks[-1],
                           broken_time_reduction_pp=float(np.mean(broken))))
    values = np.asarray(blocks)
    observed = float(values.mean())
    signs = np.asarray(list(itertools.product([-1, 1], repeat=len(values))))
    p = float(np.mean(np.abs((signs*values).mean(axis=1)) >= abs(observed)-1e-12))
    rng = np.random.default_rng(20261029)
    boot = values[rng.integers(0, len(values), (draws, len(values)))].mean(axis=1)
    reduction = float(100*(1-np.exp(observed)))
    broken = float(np.mean([d['broken_time_reduction_pp'] for d in detail]))
    return dict(treatment=treatment, baseline=baseline, cases=cases, seeds=seeds, n_seed_blocks=len(seeds),
                geometric_rmse_reduction_pct=reduction,
                bootstrap95_reduction_pct=[float(x) for x in np.percentile(100*(1-np.exp(boot)), [2.5, 97.5])],
                blocks_favoring_treatment=int((values < 0).sum()),
                exact_two_sided_sign_flip_p=p, enumerated_sign_patterns=len(signs),
                mean_broken_time_reduction_pp=broken,
                meets_practical_target=bool(reduction >= 20 and broken > 0), seed_blocks=detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--truncated', action='store_true',
                        help='Amendment A1: e01 stopped after its primary group; every primary block must still be complete')
    args = parser.parse_args()
    data = args.directory.resolve()
    manifest = json.loads((data/'manifest.json').read_text())
    payload = args.protocol.read_bytes()
    assert manifest['stage'] == 'evaluation', 'Development data are not held-out inference'
    assert manifest['protocol_sha256'] == hashlib.sha256(payload).hexdigest(), 'Protocol differs from the frozen one'
    protocol = json.loads(payload)
    results = json.loads((data/'results.json').read_text())
    assert results['complete'] or args.truncated, 'All planned evaluation runs must complete'
    # block_test() raises on any missing primary case/seed/arm, so truncation cannot hide primary data.
    spec = protocol['inference']
    alpha = spec['alpha']
    seeds = spec['seeds']
    tests, gate_open = [], True
    for order, (treatment, baseline) in enumerate(spec['fixed_sequence'], 1):
        result = block_test(results['run_results'], treatment, baseline, spec['primary_cases'], seeds)
        result['sequence_position'] = order
        result['tested_confirmatorily'] = gate_open
        result['rejected_null_at_alpha'] = bool(gate_open and result['exact_two_sided_sign_flip_p'] < alpha)
        if not result['rejected_null_at_alpha']:
            gate_open = False   # later hypotheses become descriptive only
        tests.append(result)
    output = dict(protocol_sha256=manifest['protocol_sha256'], alpha=alpha, procedure='fixed-sequence gatekeeping',
                  truncated_per_amendment_A1=bool(args.truncated and not results['complete']),
                  tests=tests, inference_assumption='Independent seed blocks; exchangeable signs under the null. '
                  'Simulator seeds are not a random sample of real oceans, cameras or vessels.')
    (data/'inference.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({k: v for k, v in output.items() if k != 'tests'}, indent=2))
    for t in tests:
        print(f"{t['sequence_position']}. {t['treatment']} vs {t['baseline']}: reduction {t['geometric_rmse_reduction_pct']:+.1f}% "
              f"CI {t['bootstrap95_reduction_pct'][0]:+.1f}..{t['bootstrap95_reduction_pct'][1]:+.1f}  p={t['exact_two_sided_sign_flip_p']:.4f} "
              f"blocks {t['blocks_favoring_treatment']}/{t['n_seed_blocks']}  confirmatory={t['tested_confirmatorily']} rejected={t['rejected_null_at_alpha']}")


if __name__ == '__main__':
    main()
