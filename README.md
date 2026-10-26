# Chromium 158.0.8116.0 → OHOS

目标是将 Google Chromium main 提交
`566635fe3ce2912169a6ca76a00a7ee1d8e400e9` 编译为 OHOS arm64 浏览器，
并接入 ../chromium-2in1-hap。132 的 OHOS 实现仅作为平台适配参考。

已使用 Google Clang 24、当前 libc++、Rust 和本机 DevEco API 26 SDK
完成浏览器主库的正式编译、链接及 HAP 打包。

当前交付候选为 native107，包名 `com.example.ohos.chromium`，与原132包独立。
已恢复密码屏幕锁定开关及中文文案；OHOS密码填充不复用设置认证的60秒有效期，
每次填充均请求系统认证。已修复加密媒体结束后窗口隐私标记未释放的问题。
菜单尺寸暂缓，DRM工作已停止。完整状态与验证范围见 [STATUS.md](STATUS.md)。

本地构建产物位于 `artifacts/`，签名后的HAP、二进制及个人签名文件不纳入Git。
[产物哈希与校验记录](artifacts/manifest.json)记录本次候选内容；主机模拟回归通过，
按用户要求安装后未启动应用、未做设备回归，因此不声称已完成真机功能验收。

本仓库保存158移植补丁、构建脚本和测试素材。`src`为本地源码工作区链接，
固定上游提交不变，实际内核改动完整保存在 `patches/` 与 `dependency-patches/`；
相邻 `chromium-2in1-hap` 独立仓库保存ArkTS/HAP工程。源码链接与生成物不提交。

```sh
python3 scripts/import_deveco_sdk.py
python3 scripts/build_native.py --stage base --jobs 8
python3 scripts/build_native.py --stage chrome --jobs 8 --keep-going 0
python3 scripts/build_hap.py --stage hap --build-mode release
```

src、sdk、toolchain-resources 和 migration 在本机指向 Linux 文件系统，
避免 WSL Windows 挂载盘的大量源码 I/O。versions.json 固定源码和参考版本。

patches/series 保存实际补丁序列，overlay/ 保存新增构建文件的可读副本。
修改源码后，导出并在原始固定提交的文件上逐文件重放验证：

```sh
python3 scripts/export_port.py
python3 scripts/apply_port.py --check
```

`dependency-patches/` 单独记录 V8、Dawn、SwiftShader、WebRTC、Skia、ANGLE、FFmpeg、Vulkan Loader、PDFium 的官方 DEPS 提交上的
改动，导出脚本会核对 Chromium 固定的 Git 提交并重放验证。

如需补充官方依赖，可运行 `python3 scripts/sync_chromium.py --mirror --deps`。
gclient 的源码 solution 为 unmanaged，保留移植改动；大型测试数据按需补齐。
不要为了继续构建重新同步或覆盖整个源码树。

已选择本机 DevEco Studio 26.0.0.851 内置的 API 26 SDK，版本 26.0.0.105。
`import_deveco_sdk.py` 将其原生部分复制到 Linux 镜像，再使用 Google Clang 24
编译。compiler-rt/CRT 引用这套 API 26 SDK 的运行库，未从 LLVM 24 重建。
来源和构建结果见 `reports/sdk-api26.json`、
`reports/api26-base-adapter-build.json`。SDK 路径不同时可传 `--sdk-root`。
HAP 使用 Windows DevEco Studio 配套的 Hvigor 6.26.8，SDK 版本值为 `26.0.0`。
两个模块的 ArkTS 和完整应用的 assembleHap 已编译通过；`--stage hap`
会校验并复制本次原生库和资源，再执行 Windows Hvigor 打包。

独立 ABI 探针结果见 [reports/abi-probe.json](reports/abi-probe.json)，
Rust 构建结果见 [reports/rust-ohos-build.json](reports/rust-ohos-build.json)。
编译和包内容校验不代表已完成设备运行验证。HAP 工程的 JSON5 修复单独保存在
hap-patches/。
