// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Copyright (c) 2023 Huawei Device Co., Ltd.
 */

#include <linux/sched.h>
#include <linux/types.h>
#include "avc.h"
#include "jit_process.h"

DEFINE_SPINLOCK(rbtree_lock);

struct result_of_find_process find_process_jit_space(struct rb_root *root, int pid)
{
	struct rb_node **node = &(root->rb_node), *parent = NULL;
	struct result_of_find_process result = {NULL, NULL, NULL};

	spin_lock(&rbtree_lock);
	while (*node) {
		struct jit_process *now = container_of(*node, struct jit_process, node);

		parent = *node;
		if (now->pid == pid) {
			result.head = &(now->head);
			break;
		}
		else if (now->pid < pid) {
			node = &((*node)->rb_left);
		}
		else if (now->pid > pid) {
			node = &((*node)->rb_right);
		}
	}
	spin_unlock(&rbtree_lock);

	result.node = node;
	result.parent = parent;
	return result;
}

struct list_head *update_process_jit_space(struct rb_root *root,
	int pid, unsigned long cookie, unsigned long *err)
{
	struct result_of_find_process result = find_process_jit_space(root, pid);

	if (result.head != NULL) {
		// find node which already exist
		struct jit_process *now = container_of(result.head, struct jit_process, head);
		if (now->cookie == cookie) {
			return result.head;
		} else {
			*err = -EACCES;
			return NULL;
		}
	} else {
	// init node
		struct jit_process *process = kmalloc(sizeof(struct jit_process), GFP_KERNEL);
		if (process == NULL) {
			jit_memory_log_error("malloc for rbTree node failed");
			*err = -ENOMEM;
			return NULL;
		}
		process->cookie = cookie;
		process->pid = pid;
		process->head.next = &(process->head);
		process->head.prev = &(process->head);
		/* Add new node and rebalance tree. */
		spin_lock(&rbtree_lock);
		rb_link_node(&(process->node), result.parent, result.node);
		rb_insert_color(&(process->node), root);
		spin_unlock(&rbtree_lock);

		return &(process->head);
	}
}

struct jit_process *delete_process_jit_space(struct rb_root *root, int pid)
{
	struct list_head *head = (find_process_jit_space(root, pid).head);
	if (head == NULL)
		return NULL;

	struct jit_process *victim = container_of(head, struct jit_process, head);
	if (victim == NULL)
		return NULL;

	spin_lock(&rbtree_lock);
	rb_erase(&(victim->node), root);
	spin_unlock(&rbtree_lock);

	return victim;
}