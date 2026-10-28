// Alpha-blended particle shader for BoatSternWake spray (vertex colour × texture).
// Lives in Resources so it is always included in player builds, unlike the
// built-in legacy particle shaders.
Shader "Hidden/USV/FoamParticle"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
    }
    SubShader
    {
        Tags { "Queue"="Transparent+100" "RenderType"="Transparent" "IgnoreProjector"="True" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #include "UnityCG.cginc"
            #include "USVOceanSurface.cginc"
            sampler2D _usvWakeTex;
            float4 _usvWakeRect;
            float _usvWakeOn, _usvOceanBaseHeight;

            sampler2D _MainTex;
            float4 _MainTex_ST;

            struct appdata
            {
                float4 vertex : POSITION;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
                float3 worldPos : TEXCOORD1;
                UNITY_FOG_COORDS(2)
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.color = v.color;
                o.worldPos = mul(unity_ObjectToWorld,v.vertex).xyz;
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                UNITY_TRANSFER_FOG(o, o.pos);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                fixed4 detail=tex2D(_MainTex,i.uv);
                float luminance=dot(detail.rgb,float3(0.2126,0.7152,0.0722));
                fixed4 c=fixed4(luminance.xxx,detail.a)*i.color;
                if (_usvOceanOn > 0.5){
                    float2 uv=(i.worldPos.xz-_usvWakeRect.xy)*_usvWakeRect.w;
                    float inside=step(0,uv.x)*step(0,uv.y)*step(uv.x,1)*step(uv.y,1);
                    float wake=tex2D(_usvWakeTex,uv).r*_usvWakeOn*inside;
                    float water=_usvOceanBaseHeight+USVOceanSample(i.worldPos.xz).x+wake;
                    // Ballistic droplets merge back into the water; never draw
                    // translucent particle rectangles through the surface.
                    c.a*=saturate((i.worldPos.y-water)/0.08);
                    clip(c.a-0.003);
                }
                UNITY_APPLY_FOG(i.fogCoord, c);
                return c;
            }
            ENDCG
        }
    }
}
