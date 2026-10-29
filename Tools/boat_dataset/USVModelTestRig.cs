using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;
using UnityEngine.Rendering;

// Isolated test project only. Captures exact transmitted frames and matching
// visible-mesh identity masks. Ground truth is never supplied to control logic.
public sealed class USVModelTestRig : MonoBehaviour
{
    [Serializable] public class Job { public string output; public float duration=120; }
    [Serializable] public class Box { public string name;public int id,x,y,w,h,pixels; }
    [Serializable] public class Sample { public string hash,camera,image;public float t;public int width,height;public Box[] boxes; }
    static USVModelTestRig instance;
    Job job;Transform leader,left,right;Camera mask,overview;
    Material[] materials;Material water;
    RenderTexture target;Texture2D pixels;
    readonly Dictionary<Camera,float> last=new Dictionary<Camera,float>();
    readonly List<Renderer> renderers=new List<Renderer>();
    StreamWriter frames,motion;
    float motionTime,movingAt=-1,overviewAt;
    bool ready;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot()
    {
        string file=null;var args=Environment.GetCommandLineArgs();
        for(int i=0;i<args.Length-1;i++)if(args[i]=="-usvmodeltest")file=args[i+1];
        if(file==null)return;
        foreach(var s in FindObjectsOfType<ShipUDPInterface>()){
            s.receivePort=s.name=="Leader" ? 47302 : (s.name=="Follower_Left" ? 47300 : 47301);
            s.sendPort=s.name=="Follower_Left" ? 47310 : (s.name=="Follower_Right" ? 47311 : 9);
        }
        foreach(var w in FindObjectsOfType<WaveController>())w.listenPort=47303;
        foreach(var c in FindObjectsOfType<MainCameraStreamSender>())c.serverPort+=35000;
        instance=new GameObject("Model evaluation observer").AddComponent<USVModelTestRig>();
        instance.job=JsonUtility.FromJson<Job>(File.ReadAllText(file));
    }

    IEnumerator Start()
    {
        Directory.CreateDirectory(job.output);
        Directory.CreateDirectory(Path.Combine(job.output,"frames"));
        frames=new StreamWriter(Path.Combine(job.output,"ground-truth.jsonl"));
        motion=new StreamWriter(Path.Combine(job.output,"motion.csv"));
        motion.WriteLine("t,boat,x,y,z,speed");
        leader=GameObject.Find("Leader").transform;left=GameObject.Find("Follower_Left").transform;right=GameObject.Find("Follower_Right").transform;
        yield return null;yield return null;
        var shader=Shader.Find("Hidden/USV/DatasetIdentity");
        if(shader==null || !shader.isSupported)throw new Exception("Identity shader unavailable");
        materials=new Material[4];for(int i=0;i<4;i++){materials[i]=new Material(shader);materials[i].SetFloat("_DatasetId",i);}
        water=new Material(shader);water.SetFloat("_DatasetWater",1);
        mask=new GameObject("Model test identity camera").AddComponent<Camera>();mask.enabled=false;
        overview=new GameObject("Model test overview").AddComponent<Camera>();overview.enabled=false;
        foreach(var r in FindObjectsOfType<Renderer>())if(!(r is ParticleSystemRenderer) && !(r is TrailRenderer) && !(r is LineRenderer))renderers.Add(r);
        ready=true;Debug.Log("[ModelTest] Ready");
    }

    public static void RecordFrame(Camera camera,byte[] jpg,int width,int height)
    {
        if(instance==null || !instance.ready || camera.name!="Camera")return;
        if(!camera.transform.IsChildOf(instance.left) && !camera.transform.IsChildOf(instance.right))return;
        if(instance.last.TryGetValue(camera,out float previous) && Time.time-previous<2f)return;
        instance.last[camera]=Time.time;
        instance.Record(camera,jpg,width,height);
    }

    void Record(Camera camera,byte[] jpg,int width,int height)
    {
        if(target==null || target.width!=width || target.height!=height){
            if(target!=null){target.Release();Destroy(target);Destroy(pixels);}
            target=new RenderTexture(width,height,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.Linear);target.antiAliasing=1;target.Create();
            pixels=new Texture2D(width,height,TextureFormat.RGB24,false,true);
        }
        string hash;using(var sha=SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(jpg)).Replace("-","").ToLowerInvariant();
        string stem=(camera.transform.IsChildOf(left) ? "LeftFront" : "RightFront")+"_"+Time.time.ToString("F2",CultureInfo.InvariantCulture);
        File.WriteAllBytes(Path.Combine(job.output,"frames",stem+".jpg"),jpg);
        mask.CopyFrom(camera);mask.enabled=false;mask.targetTexture=target;
        mask.transform.SetPositionAndRotation(camera.transform.position,camera.transform.rotation);
        mask.clearFlags=CameraClearFlags.SolidColor;mask.backgroundColor=Color.black;mask.cullingMask=0;
        mask.depthTextureMode=DepthTextureMode.None;mask.allowHDR=false;mask.allowMSAA=false;mask.renderingPath=RenderingPath.Forward;
        using(var commands=new CommandBuffer{name="Synchronized model-test identity mask"}){
            foreach(var r in renderers){
                if(r==null || !r.enabled || !r.gameObject.activeInHierarchy || (camera.cullingMask&(1<<r.gameObject.layer))==0)continue;
                int id=r.transform.IsChildOf(leader) ? 1 : (r.transform.IsChildOf(left) ? 2 : (r.transform.IsChildOf(right) ? 3 : 0));
                bool surface=r.name=="Suimono_Object" || r.name=="Suimono_ObjectScale";
                if(id==0 && !surface){bool transparent=false;foreach(var m in r.sharedMaterials)if(m!=null && m.renderQueue>=3000)transparent=true;if(transparent)continue;}
                int count=r.sharedMaterials.Length;var mesh=r.GetComponent<MeshFilter>();
                if(mesh!=null && mesh.sharedMesh!=null)count=Mathf.Min(count,mesh.sharedMesh.subMeshCount);
                for(int s=0;s<count;s++)commands.DrawRenderer(r,surface ? water : materials[id],s,0);
            }
            mask.AddCommandBuffer(CameraEvent.BeforeForwardOpaque,commands);
            try{mask.Render();}finally{mask.RemoveCommandBuffer(CameraEvent.BeforeForwardOpaque,commands);}
        }
        var previousActive=RenderTexture.active;
        try{RenderTexture.active=target;pixels.ReadPixels(new Rect(0,0,width,height),0,0,false);pixels.Apply(false);}
        finally{RenderTexture.active=previousActive;}
        File.WriteAllBytes(Path.Combine(job.output,"frames",stem+"_mask.png"),pixels.EncodeToPNG());
        var p=pixels.GetPixels32();var boxes=new List<Box>();
        for(int id=1;id<=3;id++){
            int x0=width,y0=height,x1=-1,y1=-1,n=0;
            for(int y=0;y<height;y++)for(int x=0;x<width;x++)if(p[y*width+x].r==id){n++;x0=Mathf.Min(x0,x);y0=Mathf.Min(y0,y);x1=Mathf.Max(x1,x);y1=Mathf.Max(y1,y);}
            if(n>=16 && x1-x0>=2 && y1-y0>=2)boxes.Add(new Box{id=id,name=id==1 ? "Leader" : (id==2 ? "Follower_Left" : "Follower_Right"),x=x0,y=height-1-y1,w=x1-x0+1,h=y1-y0+1,pixels=n});
        }
        frames.WriteLine(JsonUtility.ToJson(new Sample{hash=hash,camera=camera.transform.IsChildOf(left) ? "LeftFront" : "RightFront",image="frames/"+stem+".jpg",t=Time.time,width=width,height=height,boxes=boxes.ToArray()}));frames.Flush();
    }

    void Update()
    {
        if(!ready)return;
        if(movingAt<0 && leader.GetComponent<Rigidbody>().velocity.magnitude>1f)movingAt=Time.time;
        if(Time.time-motionTime>=0.2f){motionTime=Time.time;
            foreach(var b in new[]{leader,left,right}){var p=b.position;motion.WriteLine(string.Format(CultureInfo.InvariantCulture,"{0:F3},{1},{2:F3},{3:F3},{4:F3},{5:F3}",Time.time,b.name,p.x,p.y,p.z,b.GetComponent<Rigidbody>().velocity.magnitude));}motion.Flush();}
        if(movingAt>0 && Time.time-overviewAt>=15f){overviewAt=Time.time;
            Vector3 f=leader.TransformDirection(Vector3.up);f.y=0;f.Normalize();
            overview.transform.position=leader.position-f*45f+Vector3.up*110f;
            overview.transform.rotation=Quaternion.LookRotation(Vector3.down,f);overview.orthographic=true;overview.orthographicSize=85f;overview.farClipPlane=500f;
            var rt=RenderTexture.GetTemporary(960,540,24);var prev=RenderTexture.active;
            var image=new Texture2D(960,540,TextureFormat.RGB24,false);
            try{overview.targetTexture=rt;overview.Render();RenderTexture.active=rt;image.ReadPixels(new Rect(0,0,960,540),0,0);image.Apply();File.WriteAllBytes(Path.Combine(job.output,"overview_"+Time.time.ToString("F0",CultureInfo.InvariantCulture)+".jpg"),image.EncodeToJPG(85));}
            finally{overview.targetTexture=null;RenderTexture.active=prev;RenderTexture.ReleaseTemporary(rt);Destroy(image);}
        }
        if((movingAt>0 && Time.time-movingAt>=job.duration) || Time.time>job.duration+75f){
            frames.Close();motion.Close();frames=null;motion=null;
            File.WriteAllText(Path.Combine(job.output,"complete"),"completed");
            Debug.Log("[ModelTest] Complete");Application.Quit();ready=false;
        }
    }
    void OnDestroy(){if(frames!=null)frames.Dispose();if(motion!=null)motion.Dispose();}
}
