#include "build/build_config.h"

#if defined(TEST_TARGET_OHOS)
_Static_assert(BUILDFLAG(IS_OHOS), "OHOS target detection failed");
_Static_assert(BUILDFLAG(IS_POSIX), "OHOS needs the POSIX family");
_Static_assert(!BUILDFLAG(IS_LINUX), "Do not select desktop Linux APIs on OHOS");
_Static_assert(!BUILDFLAG(IS_ANDROID), "Do not select Android APIs on OHOS");
_Static_assert(sizeof(void*) == 8, "The OHOS port initially targets arm64");
#else
_Static_assert(BUILDFLAG(IS_LINUX), "Linux host platform detection regressed");
_Static_assert(BUILDFLAG(IS_POSIX), "Linux host POSIX detection regressed");
_Static_assert(!BUILDFLAG(IS_OHOS), "OHOS must not affect host tools");
#endif
