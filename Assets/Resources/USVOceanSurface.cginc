#ifndef USV_OCEAN_SURFACE_INCLUDED
#define USV_OCEAN_SURFACE_INCLUDED
    float _usvOceanOn, _usvOceanTime, _usvOceanDetail;
    float4 _usvOceanSpectrum16[16];
    float _usvOceanPhases[16];
    float4 _usvOceanRipples[6];
    // x = height in metres; yz = analytic surface slopes. Same formula as CPU.
    float3 USVOceanSample(float2 p){
        float3 value = 0;
        [unroll] for (int i = 0; i < 16; i++){
            float4 w = _usvOceanSpectrum16[i];
            float phase = dot(w.xy,p) - w.w * _usvOceanTime + _usvOceanPhases[i];
            float sn, cs; sincos(phase,sn,cs);
            value += float3(w.z*sn,w.xy*(w.z*cs));
        }
        return value * _usvOceanOn;
    }

    float2 USVOceanMicroSlope(float2 p,float footprint){
        float2 slope=0;
        [unroll] for(int i=0;i<6;i++){
            float4 w=_usvOceanRipples[i];
            float k=length(w.xy);
            float fade=1.0-smoothstep(0.25,1.0,footprint*k/6.2831853);
            float phase=dot(w.xy,p)-w.w*_usvOceanTime+_usvOceanPhases[i+5];
            slope+=(w.xy/max(k,0.001))*w.z*cos(phase)*fade;
        }
        return slope*_usvOceanDetail;
    }

    // Integrate unresolved slopes towards the horizon instead of sampling
    // sub-pixel crests as alternating bright/dark lines. Near the hull this
    // is the exact analytic slope used by buoyancy.
    float2 USVOceanFilteredSlope(float2 p,float footprint){
        float2 slope=0;
        [unroll] for(int i=0;i<16;i++){
            float4 w=_usvOceanSpectrum16[i];
            float fade=1.0-smoothstep(0.2,0.8,footprint*length(w.xy)/6.2831853);
            float phase=dot(w.xy,p)-w.w*_usvOceanTime+_usvOceanPhases[i];
            slope+=w.xy*(w.z*cos(phase)*fade);
        }
        return slope*_usvOceanOn;
    }
#endif
