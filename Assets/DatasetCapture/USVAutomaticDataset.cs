using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using UnityEngine;
using UnityEngine.Rendering;
using Suimono.Core;

// Opt-in capture harness. Normal Play mode is unaffected unless the player is
// launched with -usvdataset <job.json>. All RGB labels come from scene identity,
// never from detector predictions. No ground truth enters the Python controller.
[DefaultExecutionOrder(10002)]
public sealed class USVAutomaticDataset : MonoBehaviour
{
    [Serializable] public class Job
    {
        public string run_id, output, split="train";
        public int seed=1, samples=24, width=640, height=360, jpeg_quality=55;
        public float interval=1f, warmup=6f, speed=18f, radius=250f, turn=1f;
        public float heading=0f, left_back=22f, right_back=22f, spacing=13f;
        public float sea=0.55f, wake=1.15f, foam=2f;
        public float sun_elevation=38f, sun_azimuth=145f, sun_intensity=1.15f;
        public float camera_yaw=0f;
        public bool spray=true;
    }
    [Serializable] public class Box
    {
        public int instance_id, class_id, x, y, width, height, visible_pixels;
        public bool truncated, camera_owner;
        public string object_name;
    }
    [Serializable] public class Frame
    {
        public string stem, run_id, split, camera, owner;
        public int sample, width, height, jpeg_quality;
        public float simulation_time;
        public Vector3 camera_position;
        public Quaternion camera_rotation;
        public Box[] boxes;
    }
    sealed class Sensor { public Camera camera; public Transform owner; public string name; }
    sealed class Draw { public Renderer renderer; public Material material; public int count; }
    static readonly CultureInfo Invariant=CultureInfo.InvariantCulture;
    static string jobFile;
    Job job;
    Transform leader,left,right;
    Rigidbody leaderBody;
    SimpleMove leaderMove;
    Quaternion leaderRotation;
    Vector3 origin,forward0,right0;
    Vector2 leftOffset,rightOffset;
    float driveTime,distance,speed;
    bool drive;
    Camera maskCamera;
    RenderTexture rgbTarget,idTarget;
    Texture2D rgbPixels,idPixels;
    Material[] idMaterials;
    Material waterMaterial;
    readonly List<Sensor> sensors=new List<Sensor>();
    readonly List<Draw> draws=new List<Draw>();
    readonly List<Material> materials=new List<Material>();
    readonly FieldInfo throttle=typeof(ShipUDPInterface).GetField("targetThrottle",BindingFlags.NonPublic|BindingFlags.Instance);
    readonly FieldInfo steer=typeof(ShipUDPInterface).GetField("targetSteer",BindingFlags.NonPublic|BindingFlags.Instance);
    StreamWriter metadata;
    int saved;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot()
    {
        var args=Environment.GetCommandLineArgs();
        for(int i=0;i<args.Length-1;i++)if(args[i]=="-usvdataset")jobFile=args[i+1];
        if(string.IsNullOrEmpty(jobFile))return;
        // Before Start: isolate every network listener from the real editor.
        int port=47200;
        foreach(var ship in FindObjectsOfType<ShipUDPInterface>()){
            ship.receivePort=port++;ship.sendPort=9;ship.holdSpawnPoseUntilLeaderMoves=false;
        }
        foreach(var wave in FindObjectsOfType<WaveController>())wave.listenPort=port++;
        foreach(var stream in FindObjectsOfType<MainCameraStreamSender>())stream.enabled=false;
        new GameObject("Automatic boat dataset capture").AddComponent<USVAutomaticDataset>();
    }

    IEnumerator Start()
    {
        job=JsonUtility.FromJson<Job>(File.ReadAllText(jobFile));
        if(job.samples<1 || job.width<64 || job.height<64 || job.interval<0.1f)
            throw new ArgumentException("Invalid capture dimensions or sampling settings");
        Directory.CreateDirectory(job.output);
        foreach(string name in new[]{"images","labels","masks"})Directory.CreateDirectory(Path.Combine(job.output,name));
        string manifest=Path.Combine(job.output,job.run_id+".jsonl");
        if(File.Exists(manifest))throw new IOException("Capture refuses to overwrite a completed/partial run: "+manifest);
        File.Copy(jobFile,Path.Combine(job.output,job.run_id+".job.json"),false);
        metadata=new StreamWriter(manifest,false);
        Application.runInBackground=true;QualitySettings.vSyncCount=0;
        Application.targetFrameRate=-1;Time.captureFramerate=12;
        UnityEngine.Random.InitState(job.seed);
        // Let water, wake and daylight components finish their normal Start.
        yield return null;yield return null;
        Configure();
        yield return new WaitForSeconds(job.warmup);
        BuildDrawList();
        for(int sample=0;sample<job.samples;sample++){
            yield return new WaitForEndOfFrame();
            foreach(var sensor in sensors)Capture(sensor,sample);
            metadata.Flush();
            Debug.Log("[Dataset] "+job.run_id+" sample="+sample+" images="+saved);
            yield return new WaitForSeconds(job.interval);
        }
        metadata.Close();metadata=null;
        File.WriteAllText(Path.Combine(job.output,job.run_id+".complete"),saved.ToString(Invariant));
        Debug.Log("[Dataset] COMPLETE "+job.run_id+" images="+saved);
        Application.Quit(0);
    }

    void Configure()
    {
        leader=GameObject.Find("Leader").transform;
        left=GameObject.Find("Follower_Left").transform;
        right=GameObject.Find("Follower_Right").transform;
        leaderBody=leader.GetComponent<Rigidbody>();leaderMove=leader.GetComponent<SimpleMove>();
        leaderMove.controlMode=SimpleMove.ControlMode.Trajectory;
        leaderMove.enabled=false; // the harness also supports left turns
        origin=leader.position;
        Quaternion yaw=Quaternion.AngleAxis(job.heading,Vector3.up);
        leaderRotation=yaw*leader.rotation;
        leaderBody.rotation=leaderRotation;
        forward0=leaderRotation*Vector3.up;forward0.y=0;forward0.Normalize();
        right0=Vector3.Cross(Vector3.up,forward0);
        leftOffset=new Vector2(-job.left_back,-job.spacing);
        rightOffset=new Vector2(-job.right_back,job.spacing);
        Place(left,leftOffset,yaw);Place(right,rightOffset,yaw);
        Physics.SyncTransforms();
        foreach(var look in FindObjectsOfType<FollowerCameraLookAt>())look.enabled=false;
        foreach(var c in FindObjectsOfType<Camera>()){
            c.enabled=false;
            Transform owner=c.transform.IsChildOf(left) ? left : (c.transform.IsChildOf(right) ? right : null);
            if(owner==null || c.GetComponent<MainCameraStreamSender>()==null)continue;
            bool front=c.name=="Camera";
            Transform target=front ? leader : (owner==left ? right : left);
            Vector3 aim=target.position+Vector3.up*0.8f-c.transform.position;
            c.transform.rotation=Quaternion.AngleAxis(job.camera_yaw*(front ? 1f : -0.6f),Vector3.up)*Quaternion.LookRotation(aim,Vector3.up);
            sensors.Add(new Sensor{camera=c,owner=owner,name=owner.name+(front ? "_front" : "_side")});
        }
        sensors.Sort((a,b)=>string.CompareOrdinal(a.name,b.name));
        if(sensors.Count!=4)throw new InvalidOperationException("Expected four mounted stream cameras; found "+sensors.Count);
        var water=FindObjectOfType<SuimonoObject>();
        water.customWaves=true;water.lgWaveHeight=job.sea;water.waveHeight=0.5f;
        water.lgWaveScale=0.04f;water.waveScale=0.45f;water.turbulenceFactor=0.12f;
        water.flowDirection=(job.seed*47)%360;
        USVWakeField.Instance.strength=job.wake;USVWakeField.Instance.foamStrength=job.foam;
        foreach(var spray in FindObjectsOfType<BoatSternWake>()){spray.strength=job.wake;spray.sprayEnabled=job.spray;}
        var daylight=FindObjectOfType<USVDaylightPresentation>();
        if(daylight!=null){daylight.enabled=false;daylight.sunElevation=job.sun_elevation;
            daylight.sunAzimuth=job.sun_azimuth;daylight.sunIntensity=job.sun_intensity;daylight.enabled=true;}
        var shader=Shader.Find("Hidden/USV/DatasetIdentity");
        if(shader==null || !shader.isSupported)throw new InvalidOperationException("Identity shader unavailable");
        idMaterials=new Material[4];
        for(int i=0;i<4;i++){idMaterials[i]=new Material(shader);idMaterials[i].SetFloat("_DatasetId",i);materials.Add(idMaterials[i]);}
        waterMaterial=new Material(shader);waterMaterial.SetFloat("_DatasetWater",1);materials.Add(waterMaterial);
        maskCamera=new GameObject("Dataset identity camera").AddComponent<Camera>();maskCamera.enabled=false;
        rgbTarget=new RenderTexture(job.width,job.height,24,RenderTextureFormat.ARGB32);
        idTarget=new RenderTexture(job.width,job.height,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.Linear);
        rgbTarget.antiAliasing=1;idTarget.antiAliasing=1;rgbTarget.Create();idTarget.Create();
        rgbPixels=new Texture2D(job.width,job.height,TextureFormat.RGB24,false);
        idPixels=new Texture2D(job.width,job.height,TextureFormat.RGB24,false,true);
        driveTime=Time.time;drive=true;
        Debug.Log("[Dataset] configured "+job.run_id+" sensors="+sensors.Count);
    }

    void Place(Transform boat,Vector2 offset,Quaternion yaw)
    {
        var rb=boat.GetComponent<Rigidbody>();
        var p=origin+forward0*offset.x+right0*offset.y;p.y=boat.position.y;
        rb.position=p;rb.rotation=yaw*boat.rotation;rb.velocity=Vector3.zero;rb.angularVelocity=Vector3.zero;
    }
    static Vector3 Forward(Transform t){Vector3 f=t.TransformDirection(Vector3.up);f.y=0;return f.normalized;}
    void FixedUpdate()
    {
        if(!drive)return;
        speed=Mathf.MoveTowards(speed,job.speed,3f*Time.fixedDeltaTime);distance+=speed*Time.fixedDeltaTime;
        float a=distance/Mathf.Max(job.radius,1f);
        float x=job.turn==0 ? 0 : Mathf.Sign(job.turn)*job.radius*(1-Mathf.Cos(a));
        float z=job.turn==0 ? distance : job.radius*Mathf.Sin(a);
        Vector3 f=job.turn==0 ? forward0 : right0*(Mathf.Sign(job.turn)*Mathf.Sin(a))+forward0*Mathf.Cos(a);
        var p=origin+right0*x+forward0*z;p.y=leaderBody.position.y;
        leaderBody.MovePosition(p);
        leaderBody.MoveRotation(leaderMove.waveAttitude*Quaternion.FromToRotation(forward0,f)*leaderRotation);
        leaderBody.velocity=new Vector3(f.x*speed,leaderBody.velocity.y,f.z*speed);leaderBody.angularVelocity=Vector3.zero;
        Drive(left,leftOffset,f);Drive(right,rightOffset,f);
    }
    void Drive(Transform boat,Vector2 offset,Vector3 f)
    {
        Vector3 r=Vector3.Cross(Vector3.up,f),target=leader.position+f*offset.x+r*offset.y;
        float along=Vector3.Dot(target-boat.position,f);
        Vector3 aim=target+f*14f-boat.position;aim.y=0;
        var rb=boat.GetComponent<Rigidbody>();var iface=boat.GetComponent<ShipUDPInterface>();
        float angle=Vector3.SignedAngle(Forward(boat),aim,Vector3.up);
        throttle.SetValue(iface,Mathf.Clamp((speed+0.6f*along)/23.4f,0,0.95f));
        steer.SetValue(iface,Mathf.Clamp(angle/15f-rb.angularVelocity.y*Mathf.Rad2Deg/60f,-1,1));
    }

    void BuildDrawList()
    {
        foreach(var renderer in FindObjectsOfType<Renderer>()){
            if(renderer is ParticleSystemRenderer || renderer is TrailRenderer || renderer is LineRenderer)continue;
            int id=renderer.transform.IsChildOf(leader) ? 1 : (renderer.transform.IsChildOf(left) ? 2 : (renderer.transform.IsChildOf(right) ? 3 : 0));
            bool water=renderer.name=="Suimono_Object" || renderer.name=="Suimono_ObjectScale";
            if(id==0 && !water){bool transparent=false;foreach(var m in renderer.sharedMaterials)if(m!=null && m.renderQueue>=3000)transparent=true;if(transparent)continue;}
            int count=renderer.sharedMaterials.Length;
            var mesh=renderer.GetComponent<MeshFilter>();
            if(mesh!=null && mesh.sharedMesh!=null)count=Mathf.Min(count,mesh.sharedMesh.subMeshCount);
            if(count>0)draws.Add(new Draw{renderer=renderer,material=water ? waterMaterial : idMaterials[id],count=count});
        }
    }

    void Capture(Sensor sensor,int sample)
    {
        string stem=job.run_id+"_"+sensor.name+"_"+sample.ToString("D4",Invariant);
        var previous=RenderTexture.active;var previousTarget=sensor.camera.targetTexture;
        float previousAspect=sensor.camera.aspect;
        try{
            sensor.camera.aspect=(float)job.width/job.height;sensor.camera.targetTexture=rgbTarget;sensor.camera.Render();
            RenderTexture.active=rgbTarget;rgbPixels.ReadPixels(new Rect(0,0,job.width,job.height),0,0,false);rgbPixels.Apply(false);
            File.WriteAllBytes(Path.Combine(job.output,"images",stem+".jpg"),rgbPixels.EncodeToJPG(job.jpeg_quality));
            maskCamera.CopyFrom(sensor.camera);maskCamera.enabled=false;maskCamera.targetTexture=idTarget;
            maskCamera.transform.SetPositionAndRotation(sensor.camera.transform.position,sensor.camera.transform.rotation);
            maskCamera.clearFlags=CameraClearFlags.SolidColor;maskCamera.backgroundColor=Color.black;
            maskCamera.cullingMask=0;maskCamera.depthTextureMode=DepthTextureMode.None;
            maskCamera.allowHDR=false;maskCamera.allowMSAA=false;maskCamera.renderingPath=RenderingPath.Forward;
            using(var commands=new CommandBuffer{name="Boat identity ground truth"}){
                foreach(var draw in draws)if(draw.renderer!=null && draw.renderer.enabled && draw.renderer.gameObject.activeInHierarchy
                    && (sensor.camera.cullingMask & (1<<draw.renderer.gameObject.layer))!=0)
                    for(int sub=0;sub<draw.count;sub++)commands.DrawRenderer(draw.renderer,draw.material,sub,0);
                maskCamera.AddCommandBuffer(CameraEvent.BeforeForwardOpaque,commands);
                try{maskCamera.Render();}finally{maskCamera.RemoveCommandBuffer(CameraEvent.BeforeForwardOpaque,commands);}
            }
            RenderTexture.active=idTarget;idPixels.ReadPixels(new Rect(0,0,job.width,job.height),0,0,false);idPixels.Apply(false);
            File.WriteAllBytes(Path.Combine(job.output,"masks",stem+".png"),idPixels.EncodeToPNG());
            var pixels=idPixels.GetPixels32();var boxes=new List<Box>();var labels=new List<string>();
            for(int id=1;id<=3;id++){
                int x0=job.width,y0=job.height,x1=-1,y1=-1,count=0;
                for(int y=0;y<job.height;y++)for(int x=0;x<job.width;x++)if(pixels[y*job.width+x].r==id){
                    count++;x0=Mathf.Min(x0,x);x1=Mathf.Max(x1,x);y0=Mathf.Min(y0,y);y1=Mathf.Max(y1,y);
                }
                int w=x1-x0+1,h=y1-y0+1;
                if(count<16 || w<3 || h<3)continue;
                int top=job.height-1-y1;string name=id==1 ? "Leader" : (id==2 ? "Follower_Left" : "Follower_Right");
                var box=new Box{instance_id=id,class_id=id==1 ? 0 : 1,x=x0,y=top,width=w,height=h,
                    visible_pixels=count,truncated=x0==0 || top==0 || x1==job.width-1 || y0==0,
                    camera_owner=name==sensor.owner.name,object_name=name};
                boxes.Add(box);
                labels.Add(string.Format(Invariant,"{0} {1:F8} {2:F8} {3:F8} {4:F8}",box.class_id,
                    (x0+w*0.5f)/job.width,(top+h*0.5f)/job.height,(float)w/job.width,(float)h/job.height));
            }
            File.WriteAllText(Path.Combine(job.output,"labels",stem+".txt"),string.Join("\n",labels)+(labels.Count>0 ? "\n" : ""));
            metadata.WriteLine(JsonUtility.ToJson(new Frame{stem=stem,run_id=job.run_id,split=job.split,camera=sensor.name,
                owner=sensor.owner.name,sample=sample,width=job.width,height=job.height,jpeg_quality=job.jpeg_quality,
                simulation_time=Time.time-driveTime,camera_position=sensor.camera.transform.position,
                camera_rotation=sensor.camera.transform.rotation,boxes=boxes.ToArray()}));saved++;
        }finally{sensor.camera.targetTexture=previousTarget;sensor.camera.aspect=previousAspect;RenderTexture.active=previous;}
    }

    void OnDestroy()
    {
        if(metadata!=null)metadata.Dispose();
        foreach(var m in materials)Destroy(m);
        if(rgbTarget!=null){rgbTarget.Release();Destroy(rgbTarget);}if(idTarget!=null){idTarget.Release();Destroy(idTarget);}
        if(rgbPixels!=null)Destroy(rgbPixels);if(idPixels!=null)Destroy(idPixels);
        if(maskCamera!=null)Destroy(maskCamera.gameObject);
    }
}
