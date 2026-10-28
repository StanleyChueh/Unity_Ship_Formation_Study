#ifndef USV_OCEAN_SURFACE_INCLUDED
#define USV_OCEAN_SURFACE_INCLUDED
    float _usvOceanOn, _usvOceanTime, _usvOceanDetail;
    float4 _usvOceanWaves[4];
    // x = height in metres; yz = analytic surface slopes. Same formula as CPU.
    float3 USVOceanSample(float2 p){
        float3 value = 0;
        [unroll] for (int i = 0; i < 4; i++){
            float4 w = _usvOceanWaves[i];
            float phase = dot(w.xy,p) - w.w * _usvOceanTime + i * 1.73;
            float sn, cs; sincos(phase,sn,cs);
            value += float3(w.z*sn,w.xy*(w.z*cs));
        }
        return value * _usvOceanOn;
    }

#endif
