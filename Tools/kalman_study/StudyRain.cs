using UnityEngine;
public sealed class StudyRain : MonoBehaviour
{
    public float amount,t,seed;
    Material material;
    void OnRenderImage(RenderTexture source,RenderTexture destination){
        if(amount<=0){Graphics.Blit(source,destination);return;}
        if(material==null)material=new Material(Shader.Find("Hidden/USV/StudyRain"));
        material.SetFloat("_Rain",amount);material.SetFloat("_StudyTime",t);material.SetFloat("_Seed",seed);
        Graphics.Blit(source,destination,material);
    }
    void OnDestroy(){if(material!=null)Destroy(material);}
}
