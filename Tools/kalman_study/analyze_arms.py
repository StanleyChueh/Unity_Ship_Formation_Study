#!/usr/bin/env python3
"""Summarize every completed multi-arm run; never drops failed outcomes.

Writes results.json, run-results.csv and MATRIX.md in the batch directory. Each
pairwise table compares a treatment arm with a baseline arm on the same case and
seed. Positive reduction = lower formation RMSE for the treatment.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from analyze import load, traces, summary
from gap_prediction import summarize as gap_summary

CONTRASTS = [('on', 'off_short'), ('on', 'off'), ('on_ego', 'off_short'), ('on_ego', 'off'), ('on_ego', 'on'), ('off', 'off_short'),
             ('on_rs', 'raw'), ('on_rs', 'off_short'), ('on_rs', 'off_rs'), ('off_rs', 'raw'), ('off_rs', 'off_short'), ('off_short', 'raw'), ('on_rs', 'raw_nogate'), ('raw', 'raw_nogate')]
LABEL = dict(on_rs='KF range/speed (d04, candidate e02)', off_rs='EMA range/speed (d04)', raw='No tracker filter (raw, d04 ctrl)', raw_nogate='No bbox filtering at all (d04 ctrl)',
             on_ego='KF+ego (d03)', on='KF (d02, candidate e01)', off='EMA 3 s', off_short='EMA 0.6 s (production OFF)')


def pairwise(records, treatment, baseline):
    table = []
    for case in sorted({r['case'] for r in records}):
        b = {r['seed']: r for r in records if r['case'] == case and r['arm'] == baseline}
        a = {r['seed']: r for r in records if r['case'] == case and r['arm'] == treatment}
        seeds = sorted(a.keys() & b.keys())
        if not seeds:
            continue
        ratio = np.array([math.log(a[s]['rmse_m']/b[s]['rmse_m']) for s in seeds])
        def mean(key, arm):
            values = [(a if arm == 'a' else b)[s][key] for s in seeds]
            return None if any(v is None for v in values) else float(np.mean(values))
        table.append(dict(case=case, treatment=treatment, baseline=baseline, seeds=seeds, n=len(seeds),
                          baseline_rmse_m=mean('rmse_m', 'b'), treatment_rmse_m=mean('rmse_m', 'a'),
                          geometric_reduction_pct=float(100*(1-math.exp(ratio.mean()))),
                          seed_reduction_pct=[float(100*(1-math.exp(x))) for x in ratio],
                          wins=int((ratio < 0).sum()),
                          baseline_iou=mean('mean_iou', 'b'), treatment_iou=mean('mean_iou', 'a'),
                          baseline_broken_pct=mean('broken_pct', 'b'), treatment_broken_pct=mean('broken_pct', 'a'),
                          baseline_gap_rmse_m=mean('scheduled_gap_rmse_m', 'b'), treatment_gap_rmse_m=mean('scheduled_gap_rmse_m', 'a'),
                          baseline_gap_log_area_mae=mean('gap_log_area_mae', 'b'), treatment_gap_log_area_mae=mean('gap_log_area_mae', 'a'),
                          baseline_gap_offset_mae=mean('gap_offset_mae', 'b'), treatment_gap_offset_mae=mean('gap_offset_mae', 'a'),
                          baseline_fresh_pct=mean('fresh_pct', 'b'), treatment_fresh_pct=mean('fresh_pct', 'a')))
    return table


def collect(data, allow_partial=False):
    manifest = json.loads((data/'manifest.json').read_text())
    records, incomplete = [], []
    for job in manifest['jobs']:
        p = Path(job['output'])
        if not ((p/'bridge.complete').exists() and (p/'unity.complete').exists()):
            incomplete.append(str(p))
            continue
        rows = load(job)
        record = summary(job, rows, traces(rows, job))
        record.update(gap_summary(rows, job))
        records.append(record)
    if incomplete and not allow_partial:
        raise RuntimeError(f'{len(incomplete)} incomplete runs: no final analysis')
    return manifest, records, incomplete


def fmt(v, spec='.2f'):
    return '—' if v is None else format(v, spec)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    data = args.directory.resolve()
    manifest, records, incomplete = collect(data, args.allow_partial)
    tables = {f'{t}_vs_{b}': pairwise(records, t, b) for t, b in CONTRASTS}
    result = dict(stage=manifest['stage'], complete=not incomplete, completed=len(records), planned=len(manifest['jobs']),
                  manifest_sha256=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),
                  analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  contrasts=tables, run_results=records, incomplete=incomplete)
    (data/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    if records:
        keys = [k for k in records[0] if k != 'events']
        with (data/'run-results.csv').open('w') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows({k: r.get(k) for k in keys} for r in records)
    lines = [f'# Multi-arm matrix ({manifest["stage"]}: {data.name})', '',
             f'{len(records)}/{len(manifest["jobs"])} planned runs complete. Positive reduction = lower follower RMSE for the treatment.', '']
    arms = sorted({r['arm'] for r in records}, key=lambda a: list(LABEL).index(a))
    lines += ['## Per-arm means', '', '| Case | Arm | n | RMSE m | IoU | Broken >10 m % | Fresh % | Gap RMSE m | Gap log-area MAE | Gap offset MAE |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for case in sorted({r['case'] for r in records}):
        for arm in arms:
            rs = [r for r in records if r['case'] == case and r['arm'] == arm]
            if not rs:
                continue
            m = lambda k: None if any(r.get(k) is None for r in rs) else float(np.mean([r[k] for r in rs]))
            lines.append(f'| {case} | {LABEL[arm]} | {len(rs)} | {fmt(m("rmse_m"))} | {fmt(m("mean_iou"), ".3f")} | {fmt(m("broken_pct"), ".1f")} | '
                         f'{fmt(m("fresh_pct"), ".1f")} | {fmt(m("scheduled_gap_rmse_m"))} | {fmt(m("gap_log_area_mae"), ".3f")} | {fmt(m("gap_offset_mae"), ".3f")} |')
    for name, table in tables.items():
        if not table:
            continue
        t, b = table[0]['treatment'], table[0]['baseline']
        lines += ['', f'## {LABEL[t]} vs {LABEL[b]}', '', '| Case | n | Baseline RMSE | Treatment RMSE | Geometric reduction | Wins | Broken % B→T | IoU B→T |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for r in table:
            lines.append(f'| {r["case"]} | {r["n"]} | {fmt(r["baseline_rmse_m"])} | {fmt(r["treatment_rmse_m"])} | {r["geometric_reduction_pct"]:+.1f}% | '
                         f'{r["wins"]}/{r["n"]} | {fmt(r["baseline_broken_pct"], ".1f")}→{fmt(r["treatment_broken_pct"], ".1f")} | '
                         f'{fmt(r["baseline_iou"], ".3f")}→{fmt(r["treatment_iou"], ".3f")} |')
    (data/'MATRIX.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
