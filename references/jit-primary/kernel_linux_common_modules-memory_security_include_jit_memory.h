// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Copyright (c) 2023 Huawei Device Co., Ltd.
 */

#ifndef _JIT_MEMORY_H
#define _JIT_MEMORY_H

#include <linux/sched.h>
#include "jit_space_list.h"
#include "jit_process.h"

extern void find_jit_memory(struct task_struct *task, unsigned long start, unsigned long size, int *err);
extern void check_jit_memory(struct task_struct *task, unsigned long cookie, unsigned long prot,
	unsigned long flag, unsigned long size, unsigned long *err);
extern void delete_jit_memory(struct task_struct *task, unsigned long start, unsigned long size, int *err);
extern void exit_jit_memory(struct task_struct *task);

static bool jit_avc_has_perm(u16 tclass, u32 requested, struct task_struct *task);

#endif //_JIT_MEMORY_H