"""Run original vision/control functions at one deterministic tick per image set."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import struct
import sys
import threading

import cv2
import numpy as np
import torch
import study_runtime as rt


def receive(sock,n):
    blocks=[]
    while n:
        block=sock.recv(n)
        if not block:raise EOFError('Unity connection closed')
        blocks.append(block);n-=len(block)
    return b''.join(blocks)


class PacketSocket:
    def __init__(self,data):self.data=json.dumps(data).encode();self.sent=None
    def recvfrom(self,n):
        if self.data is None:raise BlockingIOError()
        data=self.data;self.data=None;return data,('127.0.0.1',0)
    def sendto(self,data,address):self.sent=json.loads(data)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('job',type=Path)
    parser.add_argument('--assets',type=Path,required=True)
    args=parser.parse_args();job=json.loads(args.job.read_text());output=Path(job['output'])
    sys.path.insert(0,str(args.assets))
    torch.manual_seed(job['seed']);np.random.seed(job['seed'])
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True,warn_only=True)
    from usv import vision,control,state
    control._log_right_debug=lambda *a,**k:None
    worker=threading.Thread(target=vision.cv_processing_thread,daemon=True);worker.start()
    if not rt.ready.wait(120):raise RuntimeError('Vision did not finish initialization')
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('127.0.0.1',job['port']));listener.listen(1)
        (output/'bridge.ready').write_text('ready')
        conn,_=listener.accept();conn.settimeout(120)
        records=(output/'steps.jsonl').open('w',buffering=1)
        (output/'frames').mkdir(exist_ok=True)
        try:
            while True:
                size=struct.unpack('<i',receive(conn,4))[0]
                meta=json.loads(receive(conn,size));t=round(float(meta['t']),1);rt.clock.current=1000+t
                names=['LeftFront','LeftSide','RightFront','RightSide'];images={};hashes={}
                for name in names:
                    size=struct.unpack('<i',receive(conn,4))[0];payload=receive(conn,size)
                    frame=cv2.imdecode(np.frombuffer(payload,np.uint8),cv2.IMREAD_COLOR)
                    assert frame is not None
                    images[name]=frame;hashes[name]=hashlib.sha256(payload).hexdigest()
                    if name.endswith('Front'):
                        (output/'frames'/f'{meta["step"]:05d}_{name}.jpg').write_bytes(payload)
                released=t>=5
                state.runtime_settings.update(startup_sync_released=released,startup_sync_released_at=1005.0,
                                              startup_sync_status='released' if released else 'waiting')
                rt.batch_done.clear();rt.selection.clear();rt.raw.clear();rt.frame_names.clear()
                for name,frame in images.items():rt.frame_names[id(frame)]=name
                with state.frame_lock:
                    for name,frame in images.items():state.latest_frames[name]=frame
                rt.frames_ready.set()
                if not rt.batch_done.wait(120):raise RuntimeError('Vision tick timed out')
                if rt.error:raise RuntimeError(rt.error)
                if len(rt.raw)!=4:raise RuntimeError(f'Incomplete inference batch: {list(rt.raw)}')
                poses={b['name']:b for b in meta['boats']};leader=poses['Leader'];results={};statuses={}
                for side in ('Left','Right'):
                    b=poses['Follower_'+side]
                    packet=dict(id='Follower_'+side,x=b['x'],z=b['z'],yaw=b['yaw'],speed=b['speed'],
                                leader_x=leader['x'],leader_z=leader['z'],leader_yaw=leader['yaw'],
                                leader_forward_x=leader['fx'],leader_forward_z=leader['fz'],leader_speed=leader['speed'])
                    sock=PacketSocket(packet);results[side]=control.process_boat_vision_based(sock,0,side)
                    assert sock.sent is not None
                    v=state.vision_states[side+'Front']
                    keys=['target_detected','target_stale','target_area','target_center_offset','last_detection_time',
                          'predicted_offset','predicted_area','prediction_confidence','track_offset_velocity','track_area_velocity','target_bbox']
                    statuses[side]={k:v.get(k) for k in keys}
                    if v.get('kf') is not None:
                        statuses[side]['kf_state']=list(v['kf'].state()) if v['kf'].state() else None
                        statuses[side]['kf_offset_std']=v['kf'].offset_uncertainty()
                row=dict(meta,t=t-5,sim_time=t,raw_detections=rt.raw.copy(),selected=rt.selection.copy(),status=statuses,controls=results,image_sha256=hashes)
                if released and any(not state.formation_targets[s]['front_visual_initialized'] for s in ('Left','Right')):
                    raise RuntimeError('Stationary visual calibration failed; invalid experiment, not skipped')
                if meta['step']%100==0:print(job['case'],job['arm'],job['seed'],'t=',t-5,flush=True)
                records.write(json.dumps(row,allow_nan=False)+'\n')
                command=dict(lt=results['Left']['throttle'],ls=results['Left']['steer'],rt=results['Right']['throttle'],rs=results['Right']['steer'])
                payload=json.dumps(command).encode();conn.sendall(struct.pack('<i',len(payload))+payload)
                if t>=5+job['duration']-0.01:break
        finally:records.close();conn.close()
    (output/'calibration.json').write_text(json.dumps(state.formation_targets,indent=2))
    (output/'bridge.complete').write_text('complete')


if __name__=='__main__':main()
