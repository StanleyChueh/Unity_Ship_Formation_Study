Shader "Hidden/USV/StudyRain" {
Properties { _MainTex("Frame",2D)="white"{} }
SubShader { Cull Off ZWrite Off ZTest Always Pass { CGPROGRAM
#pragma vertex vert_img
#pragma fragment frag
#include "UnityCG.cginc"
sampler2D _MainTex;float _Rain,_StudyTime,_Seed;
float hash(float2 p){return frac(sin(dot(p,float2(127.1,311.7))+_Seed)*43758.5453);}
fixed4 frag(v2f_img i):SV_Target {
    float2 uv=i.uv;
    float drops=0;
    [unroll] for(int k=0;k<3;k++){
        float2 p=uv*float2(70+k*31,17+k*7);
        p.x+=uv.y*(11+k*3);p.y+=_StudyTime*(12+k*5);
        float2 cell=floor(p),q=frac(p);float h=hash(cell+19*k);
        float streak=(1-smoothstep(0.025,0.11,abs(q.x-0.5))) * (1-smoothstep(0.12,0.50,abs(q.y-0.5)));
        drops+=streak*step(0.58,h)*(0.3+0.7*h);
    }
    float2 ripple=float2(sin(uv.y*70+_StudyTime*5),cos(uv.x*53-_StudyTime*4))*0.0006*_Rain;
    fixed4 c=tex2D(_MainTex,uv+ripple);
    c.rgb=lerp(c.rgb,float3(0.64,0.70,0.74),saturate(drops*_Rain*0.70));
    return c;
}
ENDCG } }
}
