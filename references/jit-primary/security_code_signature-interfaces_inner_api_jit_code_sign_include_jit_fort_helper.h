/*
 * Copyright (c) 2024 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef CODE_SIGN_JIT_FORT_HELPER_H
#define CODE_SIGN_JIT_FORT_HELPER_H

#include <stdint.h>
#include <stdarg.h>
#include <sys/syscall.h>
#ifdef __aarch64__
#include <asm/hwcap.h>
#include <cstdio>
#endif

#include "errcode.h"

namespace OHOS {
namespace Security {
namespace CodeSign {
#define JITFORT_PRCTL_OPTION 0x6a6974
#define JITFORT_SWITCH_IN   3
#define JITFORT_SWITCH_OUT  4
#define JITFORT_CPU_FEATURES 7

__attribute__((always_inline)) static inline long Syscall(
    unsigned long n, unsigned long a, unsigned long b,
    unsigned long c, unsigned long d, unsigned long e)
{
#ifdef __aarch64__
    register unsigned long x8 __asm__("x8") = n;
    register unsigned long x0 __asm__("x0") = a;
    register unsigned long x1 __asm__("x1") = b;
    register unsigned long x2 __asm__("x2") = c;
    register unsigned long x3 __asm__("x3") = d;
    register unsigned long x4 __asm__("x4") = e;
    asm volatile("svc 0" : "=r"(x0) : "r"(x8), "0"(x0), "r"(x1), \
        "r"(x2), "r"(x3), "r"(x4) : "memory", "cc");
    return x0;
#else
    return CS_ERR_UNSUPPORT;
#endif
}

__attribute__((always_inline)) static int inline PrctlWrapper(
    int op, unsigned long a, unsigned long b = 0)
{
#ifdef __aarch64__
    return Syscall(SYS_prctl, op, a, b, 0, 0);
#else
    return CS_ERR_UNSUPPORT;
#endif
}

__attribute__((always_inline)) static inline bool IsSupportPACFeature()
{
#ifdef __aarch64__
    unsigned long hwcaps = static_cast<unsigned long>(PrctlWrapper(
        JITFORT_PRCTL_OPTION, JITFORT_CPU_FEATURES, 0));
    if ((hwcaps & HWCAP_PACA) && (hwcaps & HWCAP_PACG)) {
        return true;
    }
#endif
    return false;
}
}
}
}
#endif