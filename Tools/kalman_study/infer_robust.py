#!/usr/bin/env python3
"""Prospectively specified seed-block inference; never treats frames as repeats."""
import argparse
import itertools
import json
from pathlib import Path
import numpy as np


def infer(records, primary_prefixes, seeds, draws=20000):
    blocks=[];detail=[]
    for seed in seeds:
        ratios=[];broken_differences=[]
        for prefix in primary_prefixes:
            pair={r['arm']:r for r in records if r['case'].startswith(prefix+'_') and r['seed']==seed}
            if set(pair)!= {'on','off'}:raise ValueError(f'Incomplete primary block: {seed}/{prefix}')
            ratio=np.log(pair['on']['rmse_m']/pair['off']['rmse_m'])
            ratios.append(ratio)
            broken_differences.append(pair['off']['broken_pct']-pair['on']['broken_pct'])
        blocks.append(float(np.mean(ratios)))
        detail.append(dict(seed=seed,case_log_rmse_ratios=[float(r) for r in ratios],
                           mean_log_rmse_ratio=blocks[-1],mean_broken_reduction_pp=float(np.mean(broken_differences))))
    values=np.asarray(blocks);observed=float(np.mean(values))
    signs=np.asarray(list(itertools.product([-1,1],repeat=len(values))))
    permutations=(signs*values).mean(axis=1)
    p=float(np.mean(np.abs(permutations)>=abs(observed)-1e-12))
    rng=np.random.default_rng(20261029)
    boot=values[rng.integers(0,len(values),(draws,len(values)))].mean(axis=1)
    improvements=100*(1-np.exp(boot))
    reduction=float(100*(1-np.exp(observed)))
    broken=float(np.mean([r['mean_broken_reduction_pp'] for r in detail]))
    return dict(n_seed_blocks=len(seeds),primary_prefixes=primary_prefixes,seeds=seeds,seed_blocks=detail,
                geometric_rmse_reduction_pct=reduction,
                bootstrap95_reduction_pct=[float(x) for x in np.percentile(improvements,[2.5,97.5])],
                exact_two_sided_sign_flip_p=p,enumerated_sign_patterns=len(permutations),
                mean_formation_broken_time_reduction_pp=broken,
                meets_predeclared_practical_target=bool(reduction>=20 and broken>0),
                passes_two_sided_005=bool(p<.05),
                inference_assumption='Independent seed blocks and exchangeable signs under the null; this simulator experiment does not establish a real-world population effect.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--cases',default='C1,C4,C5');parser.add_argument('--seeds',required=True)
    args=parser.parse_args();data=args.directory.resolve();m=json.loads((data/'manifest.json').read_text())
    assert m['stage']=='evaluation','Development data are not held-out inference'
    results=json.loads((data/'results.json').read_text());assert results['complete']
    cases=args.cases.split(',');seeds=[int(s) for s in args.seeds.split(',')]
    assert len(seeds)==6 and len(set(seeds))==6
    assert not set(seeds)&{1701,1702,1703}
    result=infer(results['run_results'],cases,seeds)
    (data/'inference.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
