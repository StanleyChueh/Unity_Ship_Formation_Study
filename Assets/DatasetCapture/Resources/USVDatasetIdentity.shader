Shader "Hidden/USV/DatasetIdentity"
{
    Properties { _DatasetId("Instance", Float)=0 _DatasetWater("Water", Float)=0 }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        Pass
        {
            Cull Off ZWrite On ZTest LEqual
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.5
            #include "UnityCG.cginc"
            #include "../../Resources/USVOceanSurface.cginc"
            sampler2D _usvWakeTex;
            float4 _usvWakeRect;
            float _usvWakeOn, _DatasetId, _DatasetWater;
            float4 vert(float4 vertex:POSITION):SV_POSITION
            {
                float3 world=mul(unity_ObjectToWorld,vertex).xyz;
                if (_DatasetWater>0.5) {
                    float2 uv=(world.xz-_usvWakeRect.xy)*_usvWakeRect.w;
                    float inside=step(0,uv.x)*step(0,uv.y)*step(uv.x,1)*step(uv.y,1);
                    world.y+=USVOceanSample(world.xz).x+tex2Dlod(_usvWakeTex,float4(uv,0,0)).r*inside*_usvWakeOn;
                }
                return mul(UNITY_MATRIX_VP,float4(world,1));
            }
            float4 frag():SV_Target { return float4(_DatasetId/255.0,0,0,1); }
            ENDCG
        }
    }
}
