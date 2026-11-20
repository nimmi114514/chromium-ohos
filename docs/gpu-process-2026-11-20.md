# 平板 GPU 独立进程适配与模式对照

原适配层和 ArkTS 外壳对所有 tablet 添加 `--in-process-gpu`。现在仅 API 14 以下平板保留该配置，较新系统复用已有的 GPU 子进程、IPC 和 NativeWindow 传递实现。2in1 路径和 JIT 策略保持原有配置。

依据：[华为 Native 子进程接口文档](https://developer.huawei.com/consumer/cn/doc/doccenter-references/api/capi-native-child-process-h/)说明，`OH_Ability_CreateNativeChildProcess` 在 API 13 及以前不支持 Tablet，从 API 14 起支持 PC/2in1 和 Tablet。接口可用不代表所有设备固件都已完成 Chromium 路径验收。

## 共享内存调整

沿用 Chromium 158 已有的 `direct_unsafe_shared_memory_allocation` 策略，将 OHOS Renderer/GPU 纳入允许范围，通过 OHOS 现有 ashmem 实现创建非只读共享内存，减少同步代理分配。直接创建失败时仍回退到代理；只读区域及其他进程的原有策略不变，不增加权限。

分配、映射和代理失败的日志在 Release 中保留必要的大小、阶段和系统错误信息。`scripts/test_ohos_direct_shared_memory.py` 用实际生产 helper 和模拟后端检查直接成功、代理回退、全部失败及关闭直接分配四种分支；它不能替代真机验证。

## 实测范围

设备为 GEM-W00、API 26。两种桌面模式下系统设备类型均为 tablet；使用同一诊断 HAP 分别冷启动，并用应用读取的 `isSystemModePc=true/false` 确认模式。覆盖安装保留原用户数据。

| 检查 | 电脑模式 | 平板模式 |
| --- | --- | --- |
| Browser/GPU PID 不同，`inProcessGpu=false` | 通过 | 通过 |
| AVC/HEVC 1080p60 播放、跳转、像素回读、前后台恢复 | 通过 | 通过 |
| DrDc 合成线程实际执行绘制 | 通过 | 通过 |
| WebGPU 计算、纹理回读、画布/视频导入、worker、设备生命周期 | 通过 | 通过 |
| 8 个 WebGPU 设备、512 次缓冲区映射，同时保留 768 MiB 临时内存 | 通过 | 通过 |
| 主动终止 GPU 后重建，Browser 存活，WebGL/WebGPU 恢复 | 通过 | 通过 |
| RGBA NativeBuffer 共享呈现与像素正确性 | 通过 | 通过 |

压力跟踪确认 Renderer 使用直接 ashmem 分配路径；本轮未观察到分配/映射错误。RGBA 呈现测试各有 271 次 NativeBuffer 导入及释放、呈现阶段 0 次 CPU staging、显式回读阶段 1 次。此结果不代表全部资源和格式都零拷贝。

可复用脚本：`probe_gpu_process.mjs` 检查隔离和故障恢复，`probe_gpu_shared_memory.mjs` 检查缓冲区及直接分配跟踪，`probe_drdc.mjs` 和 `probe_webgpu_zero_copy.mjs` 覆盖视频、合成与共享呈现。均需本地诊断构建，正式 HAP 不保留临时远程调试参数。

## 仍有边界

早期平板测试曾出现 WebGPU 缓冲区映射分配失败，随后 GPU 恢复后无法获取 adapter；该旧故障未取得具体系统 errno。调整前同一构建在两种模式也曾通过回归，因此不能认定“平板模式必然失败”，也不能据本轮通过宣称已证明旧故障的唯一根因。

尚未测试真正的 2in1 硬件、其他平板固件、小时级稳定性或性能提升。本轮窗口/PiP 检查不构成系统分屏、小窗状态的完整验收。GPU 独立进程与 DrDc 独立合成线程是两项不同能力。
