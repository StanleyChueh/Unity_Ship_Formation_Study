#!/usr/bin/env python3
"""Render replacement-comparison plots and exact-source camera evidence."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/robust-study-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image,ImageDraw
from analyze import load,traces
from make_figures import annotated,font,shade,COLORS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();data=args.directory.resolve();out=(args.output or data/'figures').resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((data/'manifest.json').read_text());results=json.loads((data/'results.json').read_text())
    assert results['complete'],'Final figures require all planned runs'
    table=results['matrix'];records=results['run_results']
    fig,ax=plt.subplots(figsize=(12,6));y=np.arange(len(table))
    for i,row in enumerate(table):
        for seed in row['seeds']:
            pair={r['arm']:r for r in records if r['case']==row['case'] and r['seed']==seed}
            ax.plot([pair['off']['rmse_m'],pair['on']['rmse_m']],[i-.08,i+.08],color='#bbbbbb',lw=.7,zorder=1)
        for arm,shift in [('off',-.08),('on',.08)]:
            vals=[r['rmse_m'] for r in records if r['case']==row['case'] and r['arm']==arm]
            ax.scatter(vals,np.full(len(vals),i+shift),s=18,color=COLORS[arm],alpha=.7)
    ax.scatter([r['baseline_rmse_m'] for r in table],y-.08,s=85,marker='D',color=COLORS['off'],label='Matched EMA OFF mean')
    ax.scatter([r['treatment_rmse_m'] for r in table],y+.08,s=85,marker='D',color=COLORS['on'],label='Robust KF ON mean')
    ax.set_xscale('log');ax.set_yticks(y,[r['case'] for r in table]);ax.invert_yaxis();ax.legend();ax.grid(axis='x',alpha=.2)
    ax.set_xlabel('Follower position RMSE (m, logarithmic scale), motion t=15–60 s')
    ax.set_title(f'Replacement tracker — {results["stage"]}; line = matched scenario/seed, diamond = mean')
    fig.tight_layout();fig.savefig(out/'matrix.png',dpi=180);plt.close(fig)
    selections=[]
    for case in sorted({j['case'] for j in manifest['jobs']}):
        seeds=sorted({j['seed'] for j in manifest['jobs'] if j['case']==case});seed=seeds[len(seeds)//2]
        pair={j['arm']:j for j in manifest['jobs'] if j['case']==case and j['seed']==seed}
        rows={arm:load(job) for arm,job in pair.items()};trace={arm:traces(rows[arm],job) for arm,job in pair.items()}
        for arm in rows:
            for row in rows[arm]:row['_directory']=pair[arm]['output']
        fig,axes=plt.subplots(4,1,figsize=(12,10),sharex=True)
        for arm in ['off','on']:
            t=[r['t'] for r in rows[arm]]
            axes[0].plot(t,[r['rms'] for r in trace[arm]],label='Robust KF ON' if arm=='on' else 'Matched EMA OFF',color=COLORS[arm])
            axes[1].plot(t,[r['iou'] for r in trace[arm]],color=COLORS[arm])
            axes[2].plot(t,[r['status']['Left']['target_center_offset'] for r in rows[arm]],color=COLORS[arm])
            axes[3].plot(t,[r['controls']['Left']['throttle'] for r in rows[arm]],color=COLORS[arm])
        for ax in axes:shade(ax,pair['on']);ax.set_xlim(0,60)
        axes[0].set_ylabel('Follower RMS (m)');axes[0].legend();axes[1].set_ylabel('Triangle IoU')
        axes[2].set_ylabel('Left used offset');axes[3].set_ylabel('Left throttle');axes[3].set_xlabel('Seconds since leader motion starts')
        axes[0].set_title(f'{case} / preselected middle seed {seed}; gray = scheduled measurement suppression')
        fig.tight_layout();fig.savefig(out/(case+'.png'),dpi=160);plt.close(fig)
        gap=pair['on']['gap']
        times=[19.9,20+gap/2,20+gap-.1,min(59.9,22+gap)] if gap else [11.9,15,20,30]
        sheet=Image.new('RGB',(2560,850),'#161b22');draw=ImageDraw.Draw(sheet)
        draw.text((10,10),f'{case} / seed {seed} / OFF = matched EMA, ON = robust KF. White GT is evaluation-only; orange line = predicted x.',font=font(22),fill='white')
        for ri,arm in enumerate(['off','on']):
            for ci,t in enumerate(times):
                index=min(range(len(rows[arm])),key=lambda i:abs(rows[arm][i]['t']-t))
                im=annotated(rows[arm][index],arm,'Left',trace[arm][index]['rms']);im.thumbnail((640,360));sheet.paste(im,(ci*640,60+ri*395))
                selections.append(dict(case=case,seed=seed,arm=arm,t=rows[arm][index]['t'],step=rows[arm][index]['step'],
                    jpeg_sha256=rows[arm][index]['image_sha256']['LeftFront'],source=pair[arm]['output']))
        sheet.save(out/(case+'_keyframes.jpg'),quality=94)
    (out/'keyframe-selection.json').write_text(json.dumps(selections,indent=2)+'\n')
    print('Saved replacement figures and exact-source keyframe index:',out)


if __name__=='__main__':main()
