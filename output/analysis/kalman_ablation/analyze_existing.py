"""Read-only retrospective ablation of completed archives; never launches simulation."""
from pathlib import Path
import json,csv,hashlib,math,os
import numpy as np
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
BASE=ROOT/'Experiments/KalmanStudy/robust_evaluation'
ARMS=['raw_nogate','raw','off_rs','on_rs','off_short']
PAIRS=[('raw','raw_nogate','temporal_bbox_gate_and_reacquisition_bias'),('off_rs','raw','EMA_rate_and_3s_coast'),('on_rs','off_rs','KF_fusion_gate_bundle'),('on_rs','raw','KF_tracking_bundle'),('on_rs','off_short','whole_system_upgrade')]
METRICS=['rmse_m','mean_iou','broken_pct','fresh_pct','correct_measurement_pct','wrong_identity_frames','min_separation_m','steer_variation_per_s','throttle_variation_per_s']
provenance={};data={};manifest={}
for tag in ['e02','e02x','e03_laps','e04_wlaps']:
 p=BASE/tag;d=json.loads((p/'results.json').read_text());assert d['complete'] and d['completed']==d['planned']
 assert json.loads((p/'source-freeze-check.json').read_text())['status']=='passed'
 manifest[tag]=json.loads((p/'manifest.json').read_text())
 data[tag]=[dict(r,source_batch=tag) for r in d['run_results']]
 for fn in ['results.json','manifest.json','source-freeze-check.json']:
  provenance[str((p/fn).relative_to(ROOT))]=hashlib.sha256((p/fn).read_bytes()).hexdigest()
a,b=manifest['e02'],manifest['e02x'];assert a['binary_sha256']==b['binary_sha256']
diffs=[k for k in set(a['source_sha256'])|set(b['source_sha256']) if a['source_sha256'].get(k)!=b['source_sha256'].get(k)]
assert diffs==['Tools/kalman_study/run_d04.py']
primary=[r for r in data['e02'] if r['case'].split('_')[0] in ['C8','C10','W1']]
primary += [r for r in data['e02x'] if r['case'].split('_')[0] in ['C8','C10','W1'] and r['arm']=='raw_nogate']
assert len(primary)==120
for c in set(r['case'] for r in primary):
 for arm in ARMS:assert len([r for r in primary if r['case']==c and r['arm']==arm])==8
cohorts={'primary_60s_posthoc_extension':primary,'laps_135s_descriptive':data['e03_laps'],'nonfixed_weather_85s_descriptive':data['e04_wlaps']}
summary=[];contrasts=[]
for name,rows in cohorts.items():
 seen=[(r['case'],r['seed'],r['arm']) for r in rows];assert len(seen)==len(set(seen))
 for case in sorted(set(r['case'] for r in rows)):
  for arm in ARMS:
   rr=[r for r in rows if r['case']==case and r['arm']==arm]
   if not rr:continue
   x=dict(cohort=name,case=case,arm=arm,n=len(rr),seeds=[r['seed'] for r in rr],source_batches=sorted(set(r['source_batch'] for r in rr)),median_rmse_m=float(np.median([r['rmse_m'] for r in rr])),catastrophic_rmse_gt50=sum(r['rmse_m']>50 for r in rr))
   for m in METRICS:
    if all(m in r for r in rr):x['mean_'+m]=float(np.mean([r[m] for r in rr]))
   summary.append(x)
  for treatment,baseline,meaning in PAIRS:
   aa={r['seed']:r for r in rows if r['case']==case and r['arm']==treatment};bb={r['seed']:r for r in rows if r['case']==case and r['arm']==baseline}
   if not aa or not bb:continue
   assert set(aa)==set(bb)
   seeds=sorted(aa);logs=[math.log(aa[s]['rmse_m']/bb[s]['rmse_m']) for s in seeds]
   contrasts.append(dict(cohort=name,case=case,treatment=treatment,baseline=baseline,interpretation=meaning,n_pairs=len(seeds),geometric_rmse_reduction_pct=100*(1-math.exp(np.mean(logs))),wins=sum(x<0 for x in logs),mean_broken_reduction_pp=float(np.mean([bb[s]['broken_pct']-aa[s]['broken_pct'] for s in seeds])),status='descriptive_posthoc_not_new_confirmatory_test'))
# Scenario-balanced block aggregation for the 3 primary cases. No new hypothesis tests.
aggregate=[]
for t,b,label in PAIRS:
 blocks=[];bd=[];ss=sorted(set(r['seed'] for r in primary))
 for seed in ss:
  aa={r['case']:r for r in primary if r['seed']==seed and r['arm']==t};bb={r['case']:r for r in primary if r['seed']==seed and r['arm']==b};assert set(aa)==set(bb) and len(aa)==3
  blocks.append(float(np.mean([math.log(aa[c]['rmse_m']/bb[c]['rmse_m']) for c in aa])))
  bd.append(float(np.mean([bb[c]['broken_pct']-aa[c]['broken_pct'] for c in aa])))
 aggregate.append(dict(treatment=t,baseline=b,interpretation=label,n_seed_blocks=len(ss),geometric_rmse_reduction_pct=100*(1-math.exp(np.mean(blocks))),blocks_favoring_treatment=sum(x<0 for x in blocks),mean_broken_reduction_pp=float(np.mean(bd)),status='descriptive_except_predeclared_e02_contrasts'))
# Numerical regression against independently archived confirmatory analysis.
inference=json.loads((BASE/'e02/inference_primary.json').read_text())
for t in inference['tests']:
 computed=next(x for x in aggregate if x['treatment']==t['treatment'] and x['baseline']==t['baseline'])
 assert abs(computed['geometric_rmse_reduction_pct']-t['geometric_rmse_reduction_pct'])<1e-9
payload=dict(scope='Retrospective analysis of existing completed data; no new simulations',provenance=provenance,cross_batch_check=dict(same_binary=True,differing_source_files=diffs,reason='runner extends raw_nogate; existing-arm patch paths retained; posthoc descriptive comparison'),summary=summary,per_case_contrasts=contrasts,primary_aggregate=aggregate,existing_confirmatory=inference)
(OUT/'ablation_results.json').write_text(json.dumps(payload,indent=2)+'\n')
for name,rr in [('per_arm_summary',summary),('paired_contrasts',contrasts),('primary_aggregate',aggregate)]:
 fields=sorted(set(k for r in rr for k in r))
 with (OUT/(name+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rr)
lines=['# Completed retrospective ablation tables','', 'Positive reduction = lower RMSE; positive broken reduction = less formation-break time. No simulations launched.','', '## Primary cases: e02 plus posthoc e02x raw_nogate','', '|Case|Method|n|Mean RMSE m|Median RMSE m|Broken %|Catastrophic >50m|','|---|---|---:|---:|---:|---:|---:|']
for r in summary:
 if r['cohort'].startswith('primary'):lines.append(f"|{r['case']}|{r['arm']}|{r['n']}|{r['mean_rmse_m']:.2f}|{r['median_rmse_m']:.2f}|{r['mean_broken_pct']:.1f}|{r['catastrophic_rmse_gt50']}/{r['n']}|")
lines+=['','## Scenario-balanced primary aggregation (8 seed blocks)','', '|Treatment|Baseline|Geometric reduction %|Blocks favoring|Broken reduction pp|','|---|---|---:|---:|---:|']
for r in aggregate:lines.append(f"|{r['treatment']}|{r['baseline']}|{r['geometric_rmse_reduction_pct']:+.2f}|{r['blocks_favoring_treatment']}/8|{r['mean_broken_reduction_pp']:+.2f}|")
for name in ['laps_135s_descriptive','nonfixed_weather_85s_descriptive']:
 lines+=['',f'## {name}: mean RMSE, all cases (2 seeds; descriptive)','', '|Case|'+'|'.join(ARMS)+'|','|---|'+'---:|'*len(ARMS)]
 for c in sorted(set(r['case'] for r in summary if r['cohort']==name)):
  vals=[]
  for a in ARMS:
   rr=[r for r in summary if r['cohort']==name and r['case']==c and r['arm']==a];vals.append(f"{rr[0]['mean_rmse_m']:.2f}" if rr else 'not run')
  lines.append('|'+c+'|'+'|'.join(vals)+'|')
(OUT/'RESULT_TABLES.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(aggregate,indent=2))
# Publication/export graphics: numeric labels retain both typical and long-tail effects in the tables.
os.environ['MPLCONFIGDIR']='/tmp/usv-ablation-mpl'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12})
for name,title,fn in [('primary_60s_posthoc_extension','Primary scenarios: mean formation RMSE (m)','primary_ablation'),('laps_135s_descriptive','Full-lap conditions: mean formation RMSE (m)','lap_ablation')]:
 cases=sorted(set(r['case'] for r in summary if r['cohort']==name));matrix=np.array([[next(r['mean_rmse_m'] for r in summary if r['cohort']==name and r['case']==c and r['arm']==a) for a in ARMS] for c in cases]);fig,ax=plt.subplots(figsize=(12.8,5.8 if len(cases)==3 else 9))
 im=ax.imshow(matrix,norm=LogNorm(vmin=2,vmax=1300),cmap='Blues',aspect='auto')
 ax.set_xticks(range(5),['No temporal\nbbox policy','Raw + bbox\nselection','EMA predictor\n3 s hold','Fusion KF\n3 s hold','Production OFF\n0.6 s hold']);ax.tick_params(axis='x',labelsize=11)
 names={'C8':'C8 clear S-turn + 2 s loss','C10':'C10 huge waves + S-turn + 2 s loss','W1':'W1 light rain: natural losses'}
 ax.set_yticks(range(len(cases)),[names.get(c.split('_')[0],c.replace('_lap_','  ').replace('_',' ')) for c in cases])
 for y in range(len(cases)):
  for x in range(5):ax.text(x,y,f'{matrix[y,x]:.1f}',ha='center',va='center',color='white' if matrix[y,x]>100 else '#16334c',fontsize=14)
 ax.set_title(title,fontsize=20,color='#003366',pad=22);fig.colorbar(im,ax=ax,label='RMSE (m), logarithmic color scale',shrink=.85)
 fig.subplots_adjust(left=.30,right=.96,top=.84,bottom=.20 if len(cases)==3 else .14)
 fig.text(.03,.055,'Descriptive ablation; lower is better. '+('8 paired seeds; raw_nogate is a later e02x extension.' if len(cases)==3 else '2 paired seeds per case; 135 s episodes. Large errors remain failures.'),fontsize=11,color='#465a70')
 fig.savefig(OUT/(fn+'.png'),dpi=180);fig.savefig(OUT/(fn+'.svg'));plt.close(fig)
print('Verified counts, freeze checks, matched seeds and archived inference; reports and plots written only to',OUT)
