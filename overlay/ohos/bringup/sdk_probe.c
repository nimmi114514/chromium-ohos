// Compile and link an OHOS ELF shared object before attempting the browser.
#include "build/build_config.h"

#include <dlfcn.h>
#include <native_window/external_window.h>
#include <pthread.h>
#include <stdint.h>
#include <unistd.h>

#if !defined(__OHOS__)
#error "The compiler must target OHOS, not an ordinary Linux or Android ABI."
#endif
#if !defined(__aarch64__)
#error "The initial port requires the AArch64 ABI."
#endif

_Static_assert(BUILDFLAG(IS_OHOS), "Chromium must recognize the OHOS platform");
_Static_assert(BUILDFLAG(IS_POSIX), "OHOS must retain the POSIX platform family");
_Static_assert(!BUILDFLAG(IS_LINUX), "OHOS must not select desktop Linux APIs");
_Static_assert(!BUILDFLAG(IS_ANDROID), "OHOS must not select Android APIs");

__attribute__((visibility("default"))) int32_t ohos_probe_surface_id(
    OHNativeWindow* window, uint64_t* surface_id) {
  return OH_NativeWindow_GetSurfaceId(window, surface_id);
}

__attribute__((visibility("default"))) long ohos_probe_page_size(void) {
  return sysconf(_SC_PAGESIZE);
}

__attribute__((visibility("default"))) int ohos_probe_pthread(void) {
  pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
  int result = pthread_mutex_lock(&mutex);
  if (result == 0)
    result = pthread_mutex_unlock(&mutex);
  pthread_mutex_destroy(&mutex);
  return result;
}

__attribute__((visibility("default"))) int ohos_probe_loader(void) {
  void* handle = dlopen("libc.so", RTLD_NOW | RTLD_LOCAL);
  if (handle == 0)
    return -1;
  return dlclose(handle);
}
