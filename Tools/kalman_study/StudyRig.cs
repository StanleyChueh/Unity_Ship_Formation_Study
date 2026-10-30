using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;
using Suimono.Core;

// Isolated research harness, not part of ordinary scene behavior. Each rendered
// observation waits for Python's real vision/control functions before advancing.
[DefaultExecutionOrder(30000)]
public sealed class StudyRig : MonoBehaviour
{
    [Serializable] public class Job { public string output;public int seed=1701,port=47500;public float duration=60,sea=0.55f,rain=0,fog=0;public bool dark=false;public string motion="circle";public float radius=720; }
    [Serializable] public class Boat { public string name;public float x,y,z,speed,fx,fz,pitch,roll,yaw; }
    [Serializable] public class Box { public int id,x,y,w,h,pixels; }
    [Serializable] public class Meta { public int step;public int width=1280,height=720;public float t,wave;public Boat[] boats;public Box[] left_boxes,right_boxes;public float left_back,left_side,right_back,right_side; }
    [Serializable] public class Command { public float lt,ls,rt,rs; }
    sealed class Sensor { public Camera camera;public string name;public StudyRain rain; }
    static string jobFile;
    Job job;Transform leader,left,right;
    Rigidbody leaderBody;SimpleMove leaderMove;Quaternion initialRotation;
    Vector3 initialForward,origin;Vector2 leftOffset,rightOffset;
    readonly List<Sensor> sensors=new List<Sensor>();
    readonly List<Renderer> renderers=new List<Renderer>();
    readonly FieldInfo throttle=typeof(ShipUDPInterface).GetField("targetThrottle",BindingFlags.NonPublic|BindingFlags.Instance);
    readonly FieldInfo steering=typeof(ShipUDPInterface).GetField("targetSteer",BindingFlags.NonPublic|BindingFlags.Instance);
    TcpClient client;NetworkStream stream;BinaryReader reader;BinaryWriter writer;
    RenderTexture rgbTarget,idTarget;Texture2D rgbPixels,idPixels;
    Camera idCamera;Material[] idMaterials;Material waterMaterial;
    SuimonoObject water;Light sun;Material sky;RenderTexture cube;
    bool ready,weatherSet;float epoch,speed,yaw;int step;
    Vector3 position;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot(){
        var args=Environment.GetCommandLineArgs();
        for(int i=0;i<args.Length-1;i++)if(args[i]=="-kalmanstudy")jobFile=args[i+1];
        if(jobFile==null)return;
        var job=JsonUtility.FromJson<Job>(File.ReadAllText(jobFile));
        UnityEngine.Random.InitState(job.seed);Time.captureFramerate=10;Application.runInBackground=true;
        QualitySettings.vSyncCount=0;Application.targetFrameRate=-1;
        int port=47600;
        foreach(var s in FindObjectsOfType<ShipUDPInterface>()){s.receivePort=port++;s.sendPort=9;s.holdSpawnPoseUntilLeaderMoves=false;}
        foreach(var w in FindObjectsOfType<WaveController>())w.listenPort=port++;
        foreach(var sender in FindObjectsOfType<MainCameraStreamSender>())sender.enabled=false;
        new GameObject("Kalman study synchronized bridge").AddComponent<StudyRig>().job=job;
    }
    IEnumerator Start(){
        yield return null;yield return null;
        leader=GameObject.Find("Leader").transform;left=GameObject.Find("Follower_Left").transform;right=GameObject.Find("Follower_Right").transform;
        leaderBody=leader.GetComponent<Rigidbody>();leaderMove=leader.GetComponent<SimpleMove>();
        leaderMove.controlMode=SimpleMove.ControlMode.Trajectory;leaderMove.enabled=false;
        origin=leader.position;position=origin;initialRotation=leader.rotation;initialForward=Forward(leader);
        var r=Vector3.Cross(Vector3.up,initialForward);
        leftOffset=new Vector2(Vector3.Dot(left.position-origin,initialForward),Vector3.Dot(left.position-origin,r));
        rightOffset=new Vector2(Vector3.Dot(right.position-origin,initialForward),Vector3.Dot(right.position-origin,r));
        foreach(var c in FindObjectsOfType<Camera>()){
            c.enabled=false;
            string owner=c.transform.IsChildOf(left) ? "Left" : (c.transform.IsChildOf(right) ? "Right" : null);
            if(owner!=null && c.GetComponent<MainCameraStreamSender>()!=null){
                var sender=c.GetComponent<MainCameraStreamSender>();
                if(sender.captureWidth!=1280 || sender.captureHeight!=720 || sender.jpgQuality!=70)throw new Exception("Study assumes current native 1280x720 JPEG70 camera configuration");
                var rain=c.gameObject.AddComponent<StudyRain>();rain.seed=job.seed;
                sensors.Add(new Sensor{camera=c,name=owner+(c.name=="Camera" ? "Front" : "Side"),rain=rain});
            }
        }
        sensors.Sort((a,b)=>Array.IndexOf(new[]{"LeftFront","LeftSide","RightFront","RightSide"},a.name).CompareTo(Array.IndexOf(new[]{"LeftFront","LeftSide","RightFront","RightSide"},b.name)));
        if(sensors.Count!=4)throw new Exception("Expected four sensors");
        water=FindObjectOfType<SuimonoObject>();water.customWaves=true;water.lgWaveHeight=0.55f;water.lgWaveScale=0.04f;
        water.waveHeight=0.5f;water.waveScale=0.45f;water.flowDirection=job.seed%720;
        USVWakeField.Instance.strength=1.15f;USVWakeField.Instance.foamStrength=2f;
        foreach(var spray in FindObjectsOfType<BoatSternWake>()){spray.strength=1.15f;spray.sprayEnabled=true;}
        var shader=Shader.Find("Hidden/USV/DatasetIdentity");
        idMaterials=new Material[4];for(int i=0;i<4;i++){idMaterials[i]=new Material(shader);idMaterials[i].SetFloat("_DatasetId",i);}
        waterMaterial=new Material(shader);waterMaterial.SetFloat("_DatasetWater",1);
        idCamera=new GameObject("Study identity camera").AddComponent<Camera>();idCamera.enabled=false;
        foreach(var renderer in FindObjectsOfType<Renderer>())if(!(renderer is ParticleSystemRenderer) && !(renderer is LineRenderer) && !(renderer is TrailRenderer))renderers.Add(renderer);
        rgbTarget=new RenderTexture(1280,720,24,RenderTextureFormat.ARGB32);rgbTarget.Create();
        idTarget=new RenderTexture(1280,720,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.Linear);idTarget.antiAliasing=1;idTarget.Create();
        rgbPixels=new Texture2D(1280,720,TextureFormat.RGB24,false);idPixels=new Texture2D(1280,720,TextureFormat.RGB24,false,true);
        client=new TcpClient("127.0.0.1",job.port);client.NoDelay=true;stream=client.GetStream();stream.ReadTimeout=120000;
        reader=new BinaryReader(stream);writer=new BinaryWriter(stream);
        epoch=Time.time;ready=true;
    }
    static Vector3 Forward(Transform b){var f=b.TransformDirection(Vector3.up);f.y=0;return f.normalized;}
    void FixedUpdate(){
        if(!ready)return;
        float t=Time.time-epoch-5;
        if(t<0)return;
        float target=18;
        if(job.motion=="variable")target=t<20 ? 14 : (t<32 ? 20 : (t<44 ? 10 : 18));
        speed=Mathf.MoveTowards(speed,target,3f*Time.fixedDeltaTime);
        float rate=speed/job.radius;
        if(job.motion=="variable")rate=0.07f*Mathf.Sin(Mathf.Max(0,t-10)*0.16f);
        if(job.motion=="unexpected")rate=t<22 ? 0 : 0.11f;
        yaw+=rate*Time.fixedDeltaTime;
        var f=Quaternion.AngleAxis(yaw*Mathf.Rad2Deg,Vector3.up)*initialForward;
        position+=f*(speed*Time.fixedDeltaTime);var p=position;p.y=leaderBody.position.y;
        leaderBody.MovePosition(p);leaderBody.MoveRotation(leaderMove.waveAttitude*Quaternion.AngleAxis(yaw*Mathf.Rad2Deg,Vector3.up)*initialRotation);
        leaderBody.velocity=new Vector3(f.x*speed,leaderBody.velocity.y,f.z*speed);leaderBody.angularVelocity=Vector3.zero;
    }
    Boat Pose(Transform b){
        var f=Forward(b);var r=Vector3.Cross(Vector3.up,f);var up=b.TransformDirection(Vector3.forward);var p=b.position;
        return new Boat{name=b.name,x=p.x,y=p.y,z=p.z,fx=f.x,fz=f.z,yaw=b.eulerAngles.y,speed=b.GetComponent<Rigidbody>().velocity.magnitude,
            pitch=Mathf.Asin(Mathf.Clamp(Vector3.Dot(up,-f),-1,1))*Mathf.Rad2Deg,roll=Mathf.Asin(Mathf.Clamp(Vector3.Dot(up,r),-1,1))*Mathf.Rad2Deg};
    }
    void SetWeather(float t){
        if(t<17)return;
        water.lgWaveHeight=job.sea;
        foreach(var s in sensors){s.rain.amount=job.rain;s.rain.t=t;}
        if(!weatherSet && (job.rain>0 || job.dark)){
            weatherSet=true;
            var daylight=FindObjectOfType<USVDaylightPresentation>();if(daylight!=null)daylight.enabled=false;
            sun=RenderSettings.sun;
            if(sun==null)foreach(var l in FindObjectsOfType<Light>())if(l.type==LightType.Directional){sun=l;break;}
            sky=new Material(Shader.Find("Skybox/Procedural"));
            sky.SetFloat("_Exposure",job.dark ? 0.06f : 0.55f);sky.SetFloat("_AtmosphereThickness",1.4f);
            sky.SetColor("_SkyTint",new Color(0.45f,0.48f,0.52f));RenderSettings.skybox=sky;
            ApplyLight();
            cube=new RenderTexture(128,128,16,RenderTextureFormat.ARGBHalf){dimension=TextureDimension.Cube,useMipMap=true,autoGenerateMips=false};cube.Create();
            var go=new GameObject("Study sky capture");var c=go.AddComponent<Camera>();c.enabled=false;c.cullingMask=0;c.clearFlags=CameraClearFlags.Skybox;c.RenderToCubemap(cube);cube.GenerateMips();Destroy(go);
            water.customRefCubemap=cube;water.reflectFallback=2;water.enableDynamicReflections=false;
        }
        if(weatherSet)ApplyLight();
    }
    void ApplyLight(){
        if(sun!=null){sun.transform.rotation=Quaternion.Euler(job.dark ? 8 : 38,145,0);sun.intensity=job.dark ? 0.07f : 0.50f;sun.color=new Color(0.82f,0.88f,1f);}
        RenderSettings.ambientMode=AmbientMode.Trilight;
        RenderSettings.ambientSkyColor=job.dark ? new Color(0.03f,0.04f,0.06f) : new Color(0.28f,0.32f,0.36f);
        RenderSettings.ambientEquatorColor=RenderSettings.ambientSkyColor*0.55f;RenderSettings.ambientGroundColor=RenderSettings.ambientSkyColor*0.2f;
        RenderSettings.fog=true;RenderSettings.fogMode=FogMode.ExponentialSquared;RenderSettings.fogDensity=job.fog;
        RenderSettings.fogColor=job.dark ? new Color(0.025f,0.035f,0.05f) : new Color(0.34f,0.39f,0.43f);
    }
    Box[] IdBoxes(Camera camera){
        idCamera.CopyFrom(camera);idCamera.enabled=false;idCamera.targetTexture=idTarget;
        idCamera.transform.SetPositionAndRotation(camera.transform.position,camera.transform.rotation);
        idCamera.clearFlags=CameraClearFlags.SolidColor;idCamera.backgroundColor=Color.black;idCamera.cullingMask=0;
        idCamera.allowHDR=false;idCamera.allowMSAA=false;idCamera.depthTextureMode=DepthTextureMode.None;idCamera.renderingPath=RenderingPath.Forward;
        using(var cb=new CommandBuffer()){
            foreach(var r in renderers){
                if(r==null || !r.enabled || !r.gameObject.activeInHierarchy || (camera.cullingMask&(1<<r.gameObject.layer))==0)continue;
                int id=r.transform.IsChildOf(leader) ? 1 : (r.transform.IsChildOf(left) ? 2 : (r.transform.IsChildOf(right) ? 3 : 0));
                bool surface=r.name=="Suimono_Object" || r.name=="Suimono_ObjectScale";
                if(id==0 && !surface){bool transparent=false;foreach(var m in r.sharedMaterials)if(m!=null && m.renderQueue>=3000)transparent=true;if(transparent)continue;}
                int count=r.sharedMaterials.Length;var mf=r.GetComponent<MeshFilter>();if(mf!=null && mf.sharedMesh!=null)count=Mathf.Min(count,mf.sharedMesh.subMeshCount);
                for(int sub=0;sub<count;sub++)cb.DrawRenderer(r,surface ? waterMaterial : idMaterials[id],sub,0);
            }
            idCamera.AddCommandBuffer(CameraEvent.BeforeForwardOpaque,cb);try{idCamera.Render();}finally{idCamera.RemoveCommandBuffer(CameraEvent.BeforeForwardOpaque,cb);}
        }
        RenderTexture.active=idTarget;idPixels.ReadPixels(new Rect(0,0,1280,720),0,0,false);idPixels.Apply(false);
        var pixels=idPixels.GetPixels32();var boxes=new List<Box>();
        for(int id=1;id<=3;id++){
            int x0=1280,y0=720,x1=-1,y1=-1,n=0;
            for(int y=0;y<720;y++)for(int x=0;x<1280;x++)if(pixels[y*1280+x].r==id){n++;x0=Mathf.Min(x0,x);y0=Mathf.Min(y0,y);x1=Mathf.Max(x1,x);y1=Mathf.Max(y1,y);}
            if(n>=16 && x1-x0>=2 && y1-y0>=2)boxes.Add(new Box{id=id,x=x0,y=359-y1,w=x1-x0+1,h=y1-y0+1,pixels=n});
        }
        return boxes.ToArray();
    }
    void LateUpdate(){
        if(!ready)return;
        try{Step();}catch(Exception ex){Debug.LogException(ex);ready=false;if(client!=null)client.Close();Application.Quit(1);}
    }
    void Step(){
        float t=Time.time-epoch;
        SetWeather(t);
        var previous=RenderTexture.active;var images=new List<byte[]>();Box[] lb=null,rb=null;
        try{
            foreach(var s in sensors){
                var old=s.camera.targetTexture;s.camera.targetTexture=rgbTarget;s.camera.aspect=1280f/720;
                s.camera.Render();RenderTexture.active=rgbTarget;rgbPixels.ReadPixels(new Rect(0,0,1280,720),0,0,false);rgbPixels.Apply(false);images.Add(rgbPixels.EncodeToJPG(70));
                if(s.name=="LeftFront")lb=IdBoxes(s.camera);if(s.name=="RightFront")rb=IdBoxes(s.camera);
                s.camera.targetTexture=old;
            }
        }finally{RenderTexture.active=previous;}
        var meta=new Meta{step=step,t=t,wave=USVOceanSurface.SampleHeight(origin+new Vector3(17,0,23)),boats=new[]{Pose(leader),Pose(left),Pose(right)},
            left_boxes=lb,right_boxes=rb,left_back=leftOffset.x,left_side=leftOffset.y,right_back=rightOffset.x,right_side=rightOffset.y};
        byte[] json=Encoding.UTF8.GetBytes(JsonUtility.ToJson(meta));writer.Write(json.Length);writer.Write(json);
        foreach(var image in images){writer.Write(image.Length);writer.Write(image);}writer.Flush();
        int length=reader.ReadInt32();var command=JsonUtility.FromJson<Command>(Encoding.UTF8.GetString(reader.ReadBytes(length)));
        throttle.SetValue(left.GetComponent<ShipUDPInterface>(),command.lt);steering.SetValue(left.GetComponent<ShipUDPInterface>(),command.ls);
        throttle.SetValue(right.GetComponent<ShipUDPInterface>(),command.rt);steering.SetValue(right.GetComponent<ShipUDPInterface>(),command.rs);
        step++;
        if(t>=5+job.duration){File.WriteAllText(Path.Combine(job.output,"unity.complete"),step.ToString(CultureInfo.InvariantCulture));ready=false;client.Close();Application.Quit();}
    }
}
