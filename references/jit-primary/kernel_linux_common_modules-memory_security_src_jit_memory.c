// SPDX-License-Identifier: GPL-2.0-or-later
/*
* Copyright (c) 2023 Huawei Device Co., Ltd.
*/
#include <linux/mman.h>
#include <linux/mm_types.h>
#include <linux/sched.h>
#include <linux/mm.h>

#include "jit_memory.h"
#include "jit_space_list.h"
#include "avc.h"
#include "objsec.h"
#include <linux/version.h>

DEFINE_SPINLOCK(list_lock);

static bool jit_avc_has_perm(u16 tclass, u32 requested, struct task_struct *task)
{
	// Bypass 'init'
	if (task_pid_nr(current) == 1) {
		return false;
	}

	struct av_decision avd;
	u32 secid;
	security_cred_getsecid(task->cred, &secid);

#if (LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0))
	return (avc_has_perm_noaudit(&selinux_state, secid, secid, tclass, requested,
		AVC_STRICT, &avd) == 0);
#else
	return (avc_has_perm_noaudit(secid, secid, tclass, requested,
		AVC_STRICT, &avd) == 0);
#endif
}

void find_jit_memory(struct task_struct *task, unsigned long start, unsigned long size, int *err)
{
	if (!jit_avc_has_perm(SECCLASS_JIT_MEMORY, JIT_MEMORY__EXEC_MEM_CTRL, task))
		return;

	struct list_head *head = (find_process_jit_space(&root_tree, task->pid).head);
	if (head != NULL) {
		spin_lock(&list_lock);
		find_jit_space(head, start, size, err);
		spin_unlock(&list_lock);
	}

}

void check_jit_memory(struct task_struct *task, unsigned long cookie, unsigned long prot,
	unsigned long flag, unsigned long size, unsigned long *err)
{
	if (!jit_avc_has_perm(SECCLASS_JIT_MEMORY, JIT_MEMORY__EXEC_MEM_CTRL, task) || !(flag & MAP_ANONYMOUS))
		return;
	unsigned long start = *err;

	// check for apply EXEC mem has been removed here
	if (!(flag & MAP_JIT))
		return;

	struct list_head *head = update_process_jit_space(&root_tree, task->pid, cookie, err);
	if (IS_ERR_VALUE(*err)) {
		vm_munmap(start, size);
		return;
	}
	if (head != NULL) {
		spin_lock(&list_lock);
		update_jit_space(head, start, size);
		spin_unlock(&list_lock);
	}
}

void delete_jit_memory(struct task_struct *task, unsigned long start, unsigned long size, int *err)
{
	if (!jit_avc_has_perm(SECCLASS_JIT_MEMORY, JIT_MEMORY__EXEC_MEM_CTRL, task))
		return;

	struct list_head *head = (find_process_jit_space(&root_tree, task->pid).head);
	if (head != NULL) {
		spin_lock(&list_lock);
		delete_jit_space(head, start, size, err);
		spin_unlock(&list_lock);
	}
}

void exit_jit_memory(struct task_struct *task)
{
	if (!jit_avc_has_perm(SECCLASS_JIT_MEMORY, JIT_MEMORY__EXEC_MEM_CTRL, task))
		return;

	struct jit_process *process = delete_process_jit_space(&root_tree, task->pid);
	if (process != NULL) {
		spin_lock(&list_lock);
		exit_jit_space(&(process->head));
		spin_unlock(&list_lock);
		kfree(process);
	}
}