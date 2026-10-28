#ifndef USV_SURFACE_NOISE_INCLUDED
#define USV_SURFACE_NOISE_INCLUDED
// World-space value noise: no repeating texture tile or camera-dependent seed.
float USVHash(float2 p){
    p = frac(p * float2(0.1031,0.11369));
    p += dot(p,p.yx+33.33);
    return frac((p.x+p.y)*p.x);
}
float USVNoise(float2 p){
    float2 cell=floor(p), f=frac(p);
    float2 u=f*f*(3.0-2.0*f);
    return lerp(lerp(USVHash(cell),USVHash(cell+float2(1,0)),u.x),
                lerp(USVHash(cell+float2(0,1)),USVHash(cell+1),u.x),u.y);
}
float USVFbm(float2 p){
    float n=0.57*USVNoise(p);
    p=float2(1.61*p.x-1.19*p.y,1.19*p.x+1.61*p.y)+17.7;
    n+=0.28*USVNoise(p);
    p=float2(1.61*p.x-1.19*p.y,1.19*p.x+1.61*p.y)+31.3;
    return n+0.15*USVNoise(p);
}
float2 USVWarp(float2 p){return float2(USVNoise(p),USVNoise(p+float2(53.1,17.8)))-0.5;}
// Pixel-footprint filtering avoids moire/crawling from the drone camera.
float USVFbmFiltered(float2 p,float width){
    float n=0.57*lerp(USVNoise(p),0.5,smoothstep(0.3,0.9,width));
    p=float2(1.61*p.x-1.19*p.y,1.19*p.x+1.61*p.y)+17.7;
    n+=0.28*lerp(USVNoise(p),0.5,smoothstep(0.3,0.9,width*2.0));
    p=float2(1.61*p.x-1.19*p.y,1.19*p.x+1.61*p.y)+31.3;
    return n+0.15*lerp(USVNoise(p),0.5,smoothstep(0.3,0.9,width*4.0));
}
#endif
