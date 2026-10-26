#include <stdio.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <multimedia/player_framework/native_avcapability.h>
#include <window_manager/oh_display_manager.h>
int main(void) {
 NativeDisplayManager_DisplayInfo *info = NULL;
 int r = OH_NativeDisplayManager_CreatePrimaryDisplay(&info);
 printf("HDRPROBE display_result=%d\n",r);
 if (info) {
  if(info->hdrFormat) for(unsigned i=0;i<info->hdrFormat->hdrFormatLength;i++) printf("HDRPROBE hdr=%u\n",info->hdrFormat->hdrFormats[i]);
  if(info->colorSpace) for(unsigned i=0;i<info->colorSpace->colorSpaceLength;i++) printf("HDRPROBE colorspace=%u\n",info->colorSpace->colorSpaces[i]);
  OH_NativeDisplayManager_DestroyDisplay(info);
 }
 OH_AVCapability *cap = OH_AVCodec_GetCapabilityByCategory("video/hevc",false,HARDWARE);
 if(cap) {
  printf("HDRPROBE hevc=%s\n",OH_AVCapability_GetName(cap));
  const int32_t *values=NULL; uint32_t n=0;
  r=OH_AVCapability_GetSupportedProfiles(cap,&values,&n);
  for(unsigned i=0;r==0 && i<n;i++) printf("HDRPROBE profile=%d\n",values[i]);
  r=OH_AVCapability_GetVideoSupportedPixelFormats(cap,&values,&n);
  for(unsigned i=0;r==0 && i<n;i++) printf("HDRPROBE decoder_pixel=%d\n",values[i]);
 }
 EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY); EGLint major=0,minor=0;
 if(eglInitialize(display,&major,&minor)) {
  printf("HDRPROBE egl=%d.%d extensions=%s\n",major,minor,eglQueryString(display,EGL_EXTENSIONS));
  EGLint n=0;eglGetConfigs(display,NULL,0,&n); EGLConfig configs[256];if(n>256)n=256;eglGetConfigs(display,configs,n,&n);
  for(int i=0;i<n;i++) { EGLint red,green,blue,alpha,surface;eglGetConfigAttrib(display,configs[i],EGL_RED_SIZE,&red);eglGetConfigAttrib(display,configs[i],EGL_GREEN_SIZE,&green);eglGetConfigAttrib(display,configs[i],EGL_BLUE_SIZE,&blue);eglGetConfigAttrib(display,configs[i],EGL_ALPHA_SIZE,&alpha);eglGetConfigAttrib(display,configs[i],EGL_SURFACE_TYPE,&surface);if(red>8)printf("HDRPROBE egl_config=%d,%d,%d,%d surface=%d\n",red,green,blue,alpha,surface); }
  eglTerminate(display);
 }else printf("HDRPROBE egl_error=%x\n",eglGetError());
 return 0;
}
