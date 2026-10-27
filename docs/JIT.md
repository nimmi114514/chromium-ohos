# Chromium 158 / OHOS JIT 调查

记录日期：2026-10-27。当前设备已恢复 native107；JIT 尚未打通，以下调查不代表性能修复已通过。

## 官方支持路径

华为为应用自带 V8、LuaJIT，以及 CEF/Electron 内置虚拟机提供 `ohos.permission.kernel.ALLOW_WRITABLE_CODE_MEMORY` 受限权限申请路径。适用设备为 Tablet 和 PC/2in1；实名认证的个人或企业开发者可申请。该项为 system_basic / system_grant 权限，需权限声明和相应 Profile，不是普通运行时授权弹窗。[华为受限开放权限列表](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/restricted-permissions#ohospermissionkernelallow_writable_code_memory)

DevEco 自动签名支持申请此权限。官方区分关联注册应用与未关联注册应用，并提供调试临时 Profile 流程；发布 Profile 需按 AGC 发布流程申请。不能把所有调试场景都解释成必须等待正式审批，也不能把已有 Debug Profile 当作拥有 JIT 权限。[自动签名](https://developer.huawei.com/consumer/cn/doc/doccenter-deveco-studio/ide-signing-auto#section1172562862811)、[申请受限权限](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/declare-permissions-in-acl)

官方还要求处理坚盾守护模式：该模式可禁止应用申请匿名可写可执行内存。即使取得 ACL，也必须保留稳定回退。配套 HAP 工程的 `docs/JIT_ACL.md` 提供清单改动、申请说明及签名步骤。

## 当前构建和设备证据

后续进展：开发者已重新生成含 ALLOW_WRITABLE_CODE_MEMORY 的 Debug Profile。native112 重新签名安装后仍出现页面错误码5；native113 直接记录到渲染子进程权限为允许，但尚未完成 JavaScript 初始化，未捕获到 mprotect 失败。当前不能把权限缺失认定为剩余崩溃原因，正在取得具体断言/栈。设备在诊断间隙回退 native107。

Chromium 固定提交为 `566635fe3ce2912169a6ca76a00a7ee1d8e400e9`，版本 158.0.8116.0，V8 为 15.8.24.0。

| 项目 | 已观察结果 |
| --- | --- |
| 编译器能力 | native 编译定义包含 Sparkplug、Maglev、TurboFan、WebAssembly，未编译为 V8_JITLESS |
| 现有签名 | Debug Profile / normal APL；调查时无上述 JIT ACL 条目 |
| 原132运行策略 | `ShouldDisableJit()` 检查坚盾状态和 ALLOW_WRITABLE_CODE_MEMORY；未获允许则添加 jitless |
| native109 release HAP | 渲染子进程 permission_writable=0，policy_jitless=1 |
| native110 debug HAP | 同样 permission_writable=0，policy_jitless=1；仅改为 debuggable 未解决 |
| 匿名虚拟地址保留 | 4KiB、256MiB、1GiB、2GiB、4GiB 的 PROT_NONE 保留均成功 |
| 执行权限切换 | RW→RX 和 RW→RWX 均返回 errno 22；此错误本身不证明是哪一层策略拒绝 |
| V8 计算函数状态 | 三项测试均为 4163；当前版本状态位表明未优化、未进入 Maglev/TurboFan，liteMode 为 true |
| WebAssembly | 当前 jitless 运行时未暴露 |

以上支持“运行时确实禁用了 JIT，且现有授权存在缺口”的结论。尚未获得有权限的对照样本，不能量化 JIT 开启后的提升，也不能认定授权是全部潜在适配问题的唯一原因。

已完成的五轮中位数基线（同一设备，自生成数据）：

| 测试 | 次数 | release HAP / ms | debug HAP / ms |
| --- | ---: | ---: | ---: |
| 整数循环 | 2,000,000 | 117.2 | 115.0 |
| 浮点循环 | 700,000 | 32.5 | 31.0 |
| 数组循环 | 1,000,000 | 55.1 | 50.4 |

这些不是系统浏览器的对照结果。测试使用独立临时浏览器上下文，结果校验一致，Canvas 像素和 500 个 DOM 节点检查通过，结束后关闭测试上下文。JIT 未启用，不将基线的普通功能检查通过称作“JIT 测试通过”。

本地原始诊断记录为 `reports/native109-jitless-baseline.json`、`reports/native110-debug-jitless-baseline.json` 及对应 memory-probe-lines 文件；原始设备日志不作为公开材料自动提交。可复用的计算脚本为 `scripts/probe_jit_performance.mjs`。

## 已撤回的强开试验

native108 绕过 jitless 检查后，渲染进程出现 `Failed to reserve virtual memory for CodeRange`，伴随 SIGTRAP / 页面错误码5。这个 V8 OOM 文案不等同于物理 RAM 耗尽。未能证明可正常运行，已撤回强开参数和策略绕过，设备恢复 native107。

native109/110 的临时内存探针、CDP 和 allow-natives-syntax 参数也已从交付源码撤回。native111 的 JITFort 探针仅完成编译，未安装、未在设备执行；不把它计入验证结果。

## 对流传配置建议的核对

- 此 V8 源码定义的运行时标志是 `jitless`，未找到 `harmony-jitless` 或 `write-protect-code-memory` 标志；不要照抄未知参数。
- 编译器已存在，单独再开 GN 编译选项不能补上应用授权。`cppgc_enable_object_poisoning` 也不是权限配置。
- RW 映射用于写入且不可执行，RX 映射用于执行且不可写。双映射能解决一些 W^X 需求，但不能由此推导鸿蒙必定允许匿名可执行映射。
- 华为已核实的文档流程是声明权限并申请 Profile，未核实 `allow-writable-code-memory: true` 或 `development-mode: true` 是当前商用设备可自行获得该权限的方式，不采用手工改签名材料的办法。
- `ALLOW_EXECUTABLE_FORT_MEMORY` 的官方场景是系统 JS 引擎；不是本项目自带 V8 的等价权限。`ALLOW_USE_JITFORT_INTERFACE` 属于另一条接口适配路线，本次不混入申请或继续试探。

## 完成标准

含 ALLOW_WRITABLE_CODE_MEMORY 的调试 Profile 和渲染子进程真实授权已核实；下一步定位仍发生的信号5，并验证 V8 生成代码执行。继续检查 WebAssembly、同数据性能对照、普通网页及 Canvas/DOM 回归，并验证无授权/坚盾模式时稳定回退。只有这些证据成立后才交付 JIT 支持。
