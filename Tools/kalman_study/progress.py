#!/usr/bin/env python3
"""Summarize completed runs without changing the frozen experiment."""
import json
from pathlib import Path
from analyze import DATA,load,traces,summary,paired_table

manifest=json.loads((DATA/'manifest.json').read_text());completed=[];active=[]
for job in manifest['jobs']:
    directory=Path(job['output'])
    if (directory/'bridge.complete').exists() and (directory/'unity.complete').exists():
        cache=directory/'progress-summary.json'
        record=json.loads(cache.read_text()) if cache.exists() else None
        if record is None or 'id_box_y_correction_px' not in record:
            rows=load(job);record=summary(job,rows,traces(rows,job));cache.write_text(json.dumps(record,indent=2)+'\n')
        completed.append(record)
    elif directory.exists():
        log=directory/'python.log';lines=log.read_text().splitlines() if log.exists() else []
        active.append(dict(run=directory.name,last_log=lines[-1] if lines else 'initializing'))
matrix=paired_table(completed)
report=dict(completed=len(completed),total=len(manifest['jobs']),active=active,
            finished_primary_cases=[r for r in matrix if r['n_pairs']==3],
            run_results=completed)
(DATA/'progress.json').write_text(json.dumps(report,indent=2)+'\n')
print('Completed',len(completed),'/',len(manifest['jobs']),'Active:',active)
for row in report['finished_primary_cases']:
    print(row['case'],'OFF',round(row['baseline_rmse_m'],2),'ON',round(row['treatment_rmse_m'],2),
          'improvement',round(row['paired_improvement_pct'],1),'%','wins',row['wins'],'/3')
