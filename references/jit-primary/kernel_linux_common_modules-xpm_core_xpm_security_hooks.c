// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Copyright (c) 2023 Huawei Device Co., Ltd.
 */

#include <linux/mman.h>
#include <linux/mm_types.h>
#include <linux/version.h>

#include "avc.h"
#include "objsec.h"
#include "exec_signature_info.h"
#include "fsverity_private.h"
#include "code_sign_ext.h"
#include "dsmm_secureshield.h"
#include "xpm_common.h"
#include "xpm_debugfs.h"
#include "xpm_log.h"
#include "xpm_report.h"
#include "xpm_security_hooks.h"

enum ownerid_policy_type {
	DENY = 0,
	ALLOW,
	CHECK,
};

static uint32_t ownerid_policy[PROCESS_OWNERID_MAX][FILE_OWNERID_MAX] __ro_after_init;

static void init_ownerid_policy(void)
{
	ownerid_policy[PROCESS_OWNERID_SYSTEM][FILE_OWNERID_SYSTEM] = ALLOW;

	ownerid_policy[PROCESS_OWNERID_APP][FILE_OWNERID_SYSTEM] = ALLOW;
	ownerid_policy[PROCESS_OWNERID_APP][FILE_OWNERID_SHARED] = ALLOW;
	ownerid_policy[PROCESS_OWNERID_APP][FILE_OWNERID_APP] = CHECK;

	ownerid_policy[PROCESS_OWNERID_DEBUG][FILE_OWNERID_SYSTEM] = ALLOW;
	ownerid_policy[PROCESS_OWNERID_DEBUG][FILE_OWNERID_SHARED] = ALLOW;
	ownerid_policy[PROCESS_OWNERID_DEBUG][FILE_OWNERID_DEBUG] = ALLOW;

	ownerid_policy[PROCESS_OWNERID_COMPAT][FILE_OWNERID_SYSTEM] = ALLOW;
	ownerid_policy[PROCESS_OWNERID_COMPAT][FILE_OWNERID_COMPAT] = ALLOW;

	for (int i = 0; i < FILE_OWNERID_MAX; i++) {
		ownerid_policy[PROCESS_OWNERID_EXTEND][i] = ALLOW;
	}
}

static int check_same_ownerid(struct cs_info *pcs_info, struct cs_info *fcs_info)
{
	if ((pcs_info->id_type == fcs_info->id_type) &&
		(pcs_info->ownerid == fcs_info->ownerid)) {
		return 0;
	}

	return -EPERM;
}

int xpm_check_ownerid_policy(struct cs_info *pcs_info, struct cs_info *fcs_info)
{
	uint32_t type;

	if (!pcs_info || !fcs_info) {
		xpm_log_error("input pcs_info or fcs_info is NULL");
		return -EINVAL;
	}

	if ((pcs_info->id_type >= PROCESS_OWNERID_MAX) ||
		(fcs_info->id_type >= FILE_OWNERID_MAX)) {
		xpm_log_info("process or file ownerid exceed maximum value");
		return -EINVAL;
	}

	type = ownerid_policy[pcs_info->id_type][fcs_info->id_type];
	switch (type) {
	case DENY:
		return -EPERM;
	case ALLOW:
		return 0;
	case CHECK:
		return check_same_ownerid(pcs_info, fcs_info);
	default:
		xpm_log_error("input ownerid type is invalid: %u", type);
		break;
	}

	return -EINVAL;
}

static int xpm_get_file_cs_info(struct cs_info *fcs_info,
	struct exec_file_signature_info *info)
{
	/* exec file is dm-verity */
	if (exec_file_signature_is_dm_verity(info)) {
		code_sign_set_ownerid(fcs_info, FILE_OWNERID_SYSTEM, NULL, 0);
		return 0;
	}

	/* exec file is fs-verity */
	if (exec_file_signature_is_fs_verity(info)) {
		struct fsverity_info *vi = fsverity_get_info(info->inode);
		if (!vi) {
			xpm_log_error("get verity info failed in fs-verity");
			return -EINVAL;
		}

		fcs_info->id_type = vi->fcs_info.id_type;
		fcs_info->ownerid = vi->fcs_info.ownerid;
		return 0;
	}

	xpm_log_error("invalid code signature info type");
	return -EINVAL;
}

int xpm_get_process_cs_info(struct cs_info *pcs_info)
{
	int ret;
	struct exec_file_signature_info *info = NULL;
	struct file *exe_file = NULL;
	struct cs_info fcs_info = {0};
	struct mm_struct *mm = current->mm;

	if (!mm)
		return -EINVAL;

	/* process cs_info has not been init, just init from exe file */
	if (mm->pcs_info.id_type == PROCESS_OWNERID_UNINIT) {
		exe_file = get_task_exe_file(current);
		if (!exe_file) {
			xpm_log_error("xpm get exe_file failed");
			return -ENOEXEC;
		}

		ret = get_exec_file_signature_info(exe_file, true, &info);
		/* reduce exe_file reference count */
		fput(exe_file);
		if (ret || (info == NULL)) {
			xpm_log_error("xpm get exe_file signature info failed");
			return ret;
		}

		ret = xpm_get_file_cs_info(&fcs_info, info);
		if (ret) {
			xpm_log_error("xpm get exe_file cs info failed");
			return ret;
		}

		/* process's ownerid is correspond to file */
		mm->pcs_info.id_type = fcs_info.id_type;
		mm->pcs_info.ownerid = fcs_info.ownerid;
	}
	pcs_info->id_type = mm->pcs_info.id_type;
	pcs_info->ownerid = mm->pcs_info.ownerid;

	return 0;
}

static int xpm_check_ownerid(struct vm_area_struct *vma,
	struct exec_file_signature_info *info)
{
	int ret;
	struct cs_info pcs_info = {0};
	struct cs_info fcs_info = {0};

	ret = xpm_get_process_cs_info(&pcs_info);
	if (ret) {
		xpm_log_error("xpm get process cs_info falied");
		return ret;
	}

	ret = xpm_get_file_cs_info(&fcs_info, info);
	if (ret) {
		xpm_log_error("xpm get file cs_info falied");
		return ret;
	}

	return xpm_check_ownerid_policy(&pcs_info, &fcs_info);
}

static int xpm_avc_has_perm(u16 tclass, u32 requested)
{
	struct av_decision avd;
	u32 sid = current_sid();

#if (LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0))
	return avc_has_perm_noaudit(&selinux_state, sid, sid, tclass, requested,
		AVC_STRICT, &avd);
#else
	return avc_has_perm_noaudit(sid, sid, tclass, requested,
		AVC_STRICT, &avd);
#endif
}

static int xpm_validate_signature(struct vm_area_struct *vma,
	struct exec_file_signature_info *info)
{
	unsigned long verified_data_end, vm_addr_end;
	const struct inode *inode = (const struct inode *)info->inode;

	if (IS_ERR_OR_NULL(info)) {
		xpm_log_error("signature info is NULL");
		return -EPERM;
	}

	if(!exec_file_signature_is_fs_verity(info))
		return 0;

	vm_addr_end = (vma->vm_pgoff << PAGE_SHIFT)
					+ (vma->vm_end - vma->vm_start);
	verified_data_end = PAGE_ALIGN(fsverity_get_verified_data_size(inode));
	if (verified_data_end < vm_addr_end) {
		xpm_log_error("data is out of verified data size");
		return -EPERM;
	}

	return 0;
}

static int xpm_check_code_segment(bool is_exec, struct vm_area_struct *vma,
	struct exec_file_signature_info *info)
{
	int i;
	unsigned long vm_addr_start, vm_addr_end;
	unsigned long seg_addr_start, seg_addr_end;
	struct exec_segment_info *segments = info->code_segments;

	if (!is_exec)
		return 0;

	if (!segments) {
		xpm_log_error("code segments is NULL");
		return -EINVAL;
	}

	vm_addr_start = vma->vm_pgoff << PAGE_SHIFT;
	vm_addr_end = vm_addr_start + (vma->vm_end - vma->vm_start);

	for (i = 0; i < info->code_segment_count; i++) {
		seg_addr_start = ALIGN_DOWN(segments[i].file_offset, PAGE_SIZE);
		seg_addr_end = PAGE_ALIGN(segments[i].file_offset +
			segments[i].size);
		if ((vm_addr_start >= seg_addr_start) &&
			(vm_addr_end <= seg_addr_end))
			return 0;
	}

	return -EPERM;
}

static int xpm_check_signature(struct vm_area_struct *vma, unsigned long prot)
{
	int ret;
	bool is_exec;
	struct exec_file_signature_info *info = NULL;

	/* vma is non-executable or mmap in xpm region just return */
	is_exec = !xpm_is_anonymous_vma(vma) && (prot & PROT_EXEC);
	if (!((vma->vm_flags & VM_XPM) || is_exec))
		return 0;

	/* process has exec_no_sign permission just return */
	if (xpm_avc_has_perm(SECCLASS_XPM, XPM__EXEC_NO_SIGN) == 0)
		return 0;

	/* validate signature when vma is mmap in xpm region or executable */
	ret = get_exec_file_signature_info(vma->vm_file, is_exec, &info);
	if (ret) {
		report_mmap_event(GET_SIGN_FAIL, is_exec ? TYPE_ELF : TYPE_ABC,
			vma, prot);
		return ret;
	}

	do {
		ret = xpm_validate_signature(vma, info);
		if (ret) {
			report_mmap_event(SIGN_INVALID,
				is_exec ? TYPE_ELF : TYPE_ABC, vma, prot);
			break;
		}

		ret = xpm_check_code_segment(is_exec, vma, info);
		if (ret) {
			report_mmap_event(DATA_MMAP_CODE,
				is_exec ? TYPE_ELF : TYPE_ABC, vma, prot);
			break;
		}

		ret = xpm_check_ownerid(vma, info);
		if (ret) {
			report_mmap_event(OWNERID_INCONSISTENT,
				is_exec ? TYPE_ELF : TYPE_ABC, vma, prot);
			break;
		}
	} while (0);

	if (info)
		put_exec_file_signature_info(info);

	return ret;
}

static int xpm_check_prot(struct vm_area_struct *vma, unsigned long prot)
{
	int ret;
	bool is_anon;

	is_anon = xpm_is_anonymous_vma(vma);

	/* check for xpm region vma prot */
	if (vma->vm_flags & VM_XPM) {
		if (is_anon || (prot & PROT_EXEC)) {
			xpm_log_error("xpm region mmap not allow anonymous or exec permission");
			return -EPERM;
		}

		return 0;
	}

	/* check for anonymous vma prot, anonymous executable permission need
	 * controled by selinux
	 * in secure shield mode, all anon + x is forbidden
	 * in default mode, temporarily allow anon + x allocation
	 */
	if (vma_is_anonymous(vma) && (prot & PROT_EXEC)) {
		if (dsmm_is_secureshield_enabled()) {
			ret = -EPERM;
			report_mmap_event(ANON_EXEC, TYPE_ANON, vma, prot);
		} else {
			ret = xpm_avc_has_perm(SECCLASS_XPM, XPM__EXEC_ANON_MEM);
			if (ret) {
				ret = 0;
				report_mmap_event(ANON_EXEC, TYPE_ANON, vma, prot);
			}
		}

		return ret;
	}

	/* check for non-anonymous vma prot */
	if (!is_anon && (prot & PROT_WRITE) && (prot & PROT_EXEC)) {
		xpm_log_error("file mmap not allow write & exec permission");
		return -EPERM;
	}

	return 0;
}

static int xpm_common_check(struct vm_area_struct *vma, unsigned long prot)
{
	int ret;

	do {
		ret = xpm_check_prot(vma, prot);
		if (ret)
			break;

		ret = xpm_check_signature(vma, prot);
	} while (0);

	return xpm_ret(ret);
}

static int xpm_mmap_check(struct vm_area_struct *vma)
{
	return xpm_common_check(vma, vma->vm_flags);
}

static int xpm_mprotect_check(struct vm_area_struct *vma,
	unsigned long reqprot, unsigned long prot)
{
	(void)reqprot;

	return xpm_common_check(vma, prot);
}

static struct security_hook_list xpm_hooks[] __ro_after_init = {
	LSM_HOOK_INIT(mmap_region, xpm_mmap_check),
	LSM_HOOK_INIT(file_mprotect, xpm_mprotect_check),
};

void xpm_register_security_hooks(void)
{
	init_ownerid_policy();
	security_add_hooks(xpm_hooks, ARRAY_SIZE(xpm_hooks), "xpm");
}
