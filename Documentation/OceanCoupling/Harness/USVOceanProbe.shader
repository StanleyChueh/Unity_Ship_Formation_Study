Shader "Hidden/USV/OceanProbe" {
SubShader { Cull Off ZWrite Off ZTest Always Pass {
CGPROGRAM
#pragma vertex vert_img
#pragma fragment frag
#include "UnityCG.cginc"
#include "USVOceanSurface.cginc"
float4 _ProbeRect;
float4 frag(v2f_img i):SV_Target {return float4(USVOceanSample(_ProbeRect.xy+i.uv*_ProbeRect.z),1);}
ENDCG
}}}
