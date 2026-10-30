#!/usr/bin/env python3
"""Produce scientific plots and paired camera keyframes from the study data."""
import json
import os
from pathlib import Path
import subprocess

os.environ.setdefault('MPLCONFIGDIR','/tmp/kalman-study-figures')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image,ImageDraw,ImageFont

from analyze import DATA,REPORT,load,traces

COLORS={'on':'#1565c0','off':'#d35b22','off_matched':'#7b1fa2','on_short':'#388e3c'}


def font(size):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',size)


def shade(ax,job):
    if job['gap']:
        for start in ([20] if job['case'].startswith('C7') else [20,38,56]):
            ax.axvspan(start,min(60,start+job['gap']),color='gray',alpha=0.16)
    if job['sea']!=0.55 or job['rain']:
        ax.axvline(12,color='#607d8b',ls=':',lw=1)
    ax.grid(alpha=0.2)


def annotated(row,arm,side,rms):
    source=Path(row['_directory'])/'frames'/f'{row["step"]:05d}_{side}Front.jpg'
    image=Image.open(source).convert('RGB');draw=ImageDraw.Draw(image)
    key='left_boxes' if side=='Left' else 'right_boxes'
    gt=next((b for b in row[key] if b['id']==1),None)
    if gt:draw.rectangle((gt['x'],gt['y'],gt['x']+gt['w'],gt['y']+gt['h']),outline='white',width=3)
    selected=row['selected'][side+'Front'];bbox=selected['bbox']
    if bbox:draw.rectangle(bbox,outline='#ee44dd',width=3)
    state=row['status'][side]
    if state['target_detected']:
        x=(state['predicted_offset']+1)*0.5*image.width
        draw.line((x,image.height*0.30,x,image.height*0.75),fill='#ffb300',width=3)
    label='FRESH' if state['target_detected'] and not state['target_stale'] else ('COAST' if state['target_stale'] else 'LOST')
    caption=f'{arm.upper()}  {side}  t={row["t"]:.1f}s  {label}  RMS={rms:.1f}m  confidence={state["prediction_confidence"]:.2f}'
    draw.rectangle((0,0,image.width,48),fill='#151b26');draw.text((10,10),caption,font=font(23),fill='white')
    if selected['forced_loss']:
        draw.text((12,58),'YOLO measurement suppressed by scheduled test',font=font(22),fill='#ffb300',stroke_width=1,stroke_fill='black')
    if gt:
        cx=gt['x']+gt['w']/2;cy=gt['y']+gt['h']/2;w=max(160,gt['w']*3);h=w*0.6
        box=(int(max(0,cx-w/2)),int(max(0,cy-h/2)),int(min(image.width,cx+w/2)),int(min(image.height,cy+h/2)))
        inset=Image.open(source).crop(box);inset.thumbnail((300,180))
        image.paste(inset,(image.width-inset.width-10,image.height-inset.height-30))
        draw.text((image.width-inset.width-10,image.height-27),'RGB zoom (unaltered)',font=font(18),fill='white',stroke_width=1,stroke_fill='black')
    return image


def main():
    manifest=json.loads((DATA/'manifest.json').read_text());jobs=manifest['jobs']
    matrix=json.loads((REPORT/'matrix.json').read_text());records=json.loads((REPORT/'run-results.json').read_text())
    figures=REPORT/'figures';figures.mkdir(exist_ok=True);keyframes=REPORT/'keyframes';keyframes.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    table=matrix['primary'];y=np.arange(len(table));fig,ax=plt.subplots(figsize=(12,6))
    for i,r in enumerate(table):
        ax.plot([r['baseline_rmse_m'],r['treatment_rmse_m']],[i,i],color='#999999',lw=2)
    ax.scatter([r['baseline_rmse_m'] for r in table],y-0.08,s=65,label='Kalman OFF mean',color=COLORS['off'])
    ax.scatter([r['treatment_rmse_m'] for r in table],y+0.08,s=65,label='Kalman ON mean',color=COLORS['on'])
    ax.set_xscale('log')
    for i,r in enumerate(table):
        for arm,shift in [('off',-0.08),('on',0.08)]:
            vals=[v['rmse_m'] for v in records if v['case']==r['case'] and v['arm']==arm]
            ax.scatter(vals,np.full(len(vals),i+shift),s=16,color='black',zorder=3)
    ax.set_yticks(y,[r['case'] for r in table]);ax.invert_yaxis();ax.set_xlabel('Follower position RMSE (m, logarithmic axis), motion t=15–60 s')
    ax.set_title('Kalman system ablation: 3 paired seeds per case (dots = complete runs)');ax.legend();ax.grid(axis='x',alpha=0.2)
    fig.tight_layout();fig.savefig(figures/'matrix.png',dpi=180);plt.close(fig)

    evidence=[]
    for case in sorted({j['case'] for j in jobs}):
        pair={j['arm']:j for j in jobs if j['case']==case and j['seed']==1702}
        rows={};trace={}
        for arm,job in pair.items():
            rows[arm]=load(job)
            for r in rows[arm]:r['_directory']=job['output']
            trace[arm]=traces(rows[arm],job)
        fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True)
        for arm in pair:
            times=[r['t'] for r in trace[arm]]
            axes[0].plot(times,[r['rms'] for r in trace[arm]],label=arm,color=COLORS[arm],lw=1.6)
            axes[1].plot(times,[r['iou'] for r in trace[arm]],color=COLORS[arm],lw=1.2)
            axes[2].plot(times,[r['controls']['Left']['steer'] for r in rows[arm]],label=arm,color=COLORS[arm],lw=1.1)
        for ax in axes:shade(ax,pair['on']);ax.set_xlim(0,60)
        axes[0].axhline(10,color='black',ls='--',lw=0.8);axes[0].set_ylabel('Follower RMS (m)');axes[0].legend(ncol=4)
        axes[1].set_ylabel('Triangle IoU');axes[2].set_ylabel('Left steering');axes[2].set_xlabel('Seconds since prescribed leader motion starts')
        axes[0].set_title(case+' — predeclared seed 1702; gray = scheduled measurement suppression')
        fig.tight_layout();fig.savefig(figures/(case+'.png'),dpi=170);plt.close(fig)

        # All keyframe examples use the fixed middle seed, not the most favorable run.
        gap=pair['on']['gap']
        if gap:times=[19.8,20+gap/2,20+gap-0.1,min(59.9,21+gap)]
        else:
            missing=[r for r in trace['off'] if r['t']>=15 and not r['Left_fresh']]
            start=missing[0]['t'] if missing else 20
            times=[max(0,start-0.2),start+0.5,start+1.5,min(59.9,start+3)]
        sheet=Image.new('RGB',(2560,2*400+58),'#161b22');draw=ImageDraw.Draw(sheet)
        draw.text((12,8),case+' / seed 1702 | white = GT; magenta = used bbox; orange = predicted horizontal position',font=font(23),fill='white')
        for i,arm in enumerate(['off','on']):
            for col,t in enumerate(times):
                idx=min(range(len(rows[arm])),key=lambda n:abs(rows[arm][n]['t']-t));r=rows[arm][idx]
                image=annotated(r,arm,'Left',trace[arm][idx]['rms']);image.thumbnail((640,360))
                sheet.paste(image,(col*640,58+i*400))
        sheet.save(keyframes/(case+'.jpg'),quality=94)
        delta=np.array([o['rms']-n['rms'] for o,n in zip(trace['off'],trace['on'])]);valid=np.array([r['t']>=15 for r in trace['on']])
        for label,index in [('largest_ON_benefit',int(np.argmax(np.where(valid,delta,-np.inf)))),('largest_ON_disadvantage',int(np.argmin(np.where(valid,delta,np.inf))))]:
            evidence.append(dict(case=case,seed=1702,type=label,t=trace['on'][index]['t'],off_minus_on_rms_m=float(delta[index])))
            extreme=Image.new('RGB',(1280,770),'#161b22');d=ImageDraw.Draw(extreme)
            d.text((8,10),f'{case}: {label} (extremum, not average); OFF minus ON RMS = {delta[index]:+.2f} m',font=font(17),fill='white')
            for ri,arm in enumerate(['off','on']):
                for ci,side in enumerate(['Left','Right']):
                    image=annotated(rows[arm][index],arm,side,trace[arm][index]['rms']);image.thumbnail((640,360));extreme.paste(image,(ci*640,50+ri*360))
            extreme.save(keyframes/(case+'_'+label+'.jpg'),quality=94)

        if case.startswith(('C4','C5','C7')):
            # Camera sequence + actual leader-relative formation map. The map
            # contains evaluation ground truth, not filter world-position output.
            video_frames=DATA/'video_frames'/case;video_frames.mkdir(parents=True,exist_ok=True)
            end=32 if gap>=8 else 27
            indices=[i for i,r in enumerate(rows['on']) if 19<=r['t']<=end]
            extent=45
            for arm in ['off','on']:
                for index in indices:
                    rr=rows[arm][index];l=rr['boats'][0]
                    for b in rr['boats'][1:]:
                        dx,dz=b['x']-l['x'],b['z']-l['z']
                        extent=max(extent,abs(dx*l['fz']-dz*l['fx']),abs(dx*l['fx']+dz*l['fz']))
            scale=430/(extent+10)
            for frame,index in enumerate(indices):
                canvas=Image.new('RGB',(1920,720),'#161b22')
                for ri,arm in enumerate(['off','on']):
                    for ci,side in enumerate(['Left','Right']):
                        image=annotated(rows[arm][index],arm,side,trace[arm][index]['rms']);image.thumbnail((640,360));canvas.paste(image,(ci*640,ri*360))
                d=ImageDraw.Draw(canvas);d.text((1300,20),case,font=font(22),fill='white')
                d.text((1300,58),f'Seed 1702 / t={rows["on"][index]["t"]:.1f}s',font=font(22),fill='white')
                d.text((1300,95),'Actual leader-relative positions (GT)',font=font(20),fill='white')
                def point(right,back):return (1600+right*scale,210+back*scale)
                rr=rows['on'][index]
                ideal=[point(0,0),point(rr['left_side'],-rr['left_back']),point(rr['right_side'],-rr['right_back'])]
                d.line(ideal+[ideal[0]],fill='#999999',width=2)
                d.ellipse((1592,202,1608,218),fill='white')
                for arm in ['off','on']:
                    row=rows[arm][index];l=row['boats'][0]
                    for b in row['boats'][1:]:
                        dx,dz=b['x']-l['x'],b['z']-l['z'];q=point(dx*l['fz']-dz*l['fx'],-dx*l['fx']-dz*l['fz'])
                        d.ellipse((q[0]-7,q[1]-7,q[0]+7,q[1]+7),fill=COLORS[arm])
                    d.text((1300,600+(35 if arm=='on' else 0)),f'{arm.upper()} RMS {trace[arm][index]["rms"]:.2f} m',font=font(24),fill=COLORS[arm])
                d.text((1300,680),'Gray triangle = fixed desired formation',font=font(19),fill='white')
                canvas.save(video_frames/f'{frame:04d}.jpg',quality=90)
            subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','10','-i',str(video_frames/'%04d.jpg'),
                            '-c:v','libx264','-threads','2','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',
                            str(REPORT/(case+'.mp4'))],check=True)
    # Report extrema over every primary seed as well, including catastrophic
    # failures that the fixed middle-seed illustrations might not show.
    for case in sorted({j['case'] for j in jobs}):
        candidates=[]
        for seed in [1701,1702,1703]:
            pair={j['arm']:j for j in jobs if j['case']==case and j['seed']==seed and j['arm'] in ['off','on']}
            rr={arm:load(job) for arm,job in pair.items()}
            tt={arm:traces(rr[arm],job) for arm,job in pair.items()}
            for arm in rr:
                for row in rr[arm]:row['_directory']=pair[arm]['output']
            delta=np.array([a['rms']-b['rms'] for a,b in zip(tt['off'],tt['on'])])
            valid=np.array([r['t']>=15 for r in tt['on']])
            for label,index in [('all_seeds_largest_ON_benefit',int(np.argmax(np.where(valid,delta,-np.inf)))),('all_seeds_largest_ON_disadvantage',int(np.argmin(np.where(valid,delta,np.inf))))]:
                candidates.append((label,float(delta[index]),seed,index,rr,tt))
        for label in ['all_seeds_largest_ON_benefit','all_seeds_largest_ON_disadvantage']:
            subset=[c for c in candidates if c[0]==label]
            chosen=(max if label.endswith('benefit') else min)(subset,key=lambda c:c[1])
            _,difference,seed,index,rr,tt=chosen
            evidence.append(dict(case=case,seed=seed,type=label,t=tt['on'][index]['t'],off_minus_on_rms_m=difference))
            canvas=Image.new('RGB',(1280,770),'#161b22');d=ImageDraw.Draw(canvas)
            d.text((8,10),f'{case} / seed {seed}: {label}; OFF minus ON RMS={difference:+.2f}m',font=font(16),fill='white')
            for ri,arm in enumerate(['off','on']):
                for ci,side in enumerate(['Left','Right']):
                    im=annotated(rr[arm][index],arm,side,tt[arm][index]['rms']);im.thumbnail((640,360));canvas.paste(im,(ci*640,50+ri*360))
            canvas.save(keyframes/(case+'_'+label+'.jpg'),quality=94)
    (REPORT/'keyframe-selection.json').write_text(json.dumps(evidence,indent=2)+'\n')

    # Overview of the actual weather inputs at the same predetermined motion time.
    sheet=Image.new('RGB',(2560,440),'#161b22');draw=ImageDraw.Draw(sheet)
    for i,case in enumerate(sorted({j['case'] for j in jobs})[:4]):
        job=next(j for j in jobs if j['case']==case and j['seed']==1702 and j['arm']=='on')
        rr=load(job);r=min(rr,key=lambda r:abs(r['t']-18));image=Image.open(Path(job['output'])/'frames'/f'{r["step"]:05d}_LeftFront.jpg');image.thumbnail((640,360));sheet.paste(image,(i*640,55));draw.text((i*640+8,12),case,font=font(24),fill='white')
    sheet.save(figures/'weather-inputs.jpg',quality=94)
    print('Saved matrix, 8 time-series plots, 8 paired keyframe sheets, weather inputs and extrema index.')


if __name__=='__main__':main()
