"""Clock/barrier/inference recorder for the isolated synchronous experiment."""
import threading
import time as real_time


class Clock:
    current=1000.0
    def time(self):return self.current
    def sleep(self,seconds):real_time.sleep(min(seconds,0.01))
    def __getattr__(self,name):return getattr(real_time,name)


clock=Clock()
batch_done=threading.Event()
frames_ready=threading.Event()
ready=threading.Event()
error=None
frame_names={}
raw={}
selection={}


class AuditYOLO:
    def __init__(self,model):self.wrapped=model
    def __getattr__(self,name):return getattr(self.wrapped,name)
    def predict(self,inputs,**kwargs):
        results=self.wrapped.predict(inputs,**kwargs)
        frames=inputs if isinstance(inputs,list) else [inputs]
        for frame,result in zip(frames,results):
            name=frame_names.get(id(frame))
            if name is not None:
                raw[name]=result.boxes.data.cpu().numpy().tolist() if result.boxes is not None else []
        return results


def record_selection(name,box,area,offset,forced,confidence):
    selection[name]={'bbox':box,'area':float(area),'offset':float(offset),'forced_loss':bool(forced),'confidence':float(confidence)}
