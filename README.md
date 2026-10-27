# Chromium for OHOS

将 **Chromium 158.0.8116.0** 移植到 **OHOS / HarmonyOS arm64** 的社区项目，面向平板与 2in1 设备，当前使用 **API 26** SDK 构建。

本仓库保存内核及依赖的适配补丁、构建工具和验证记录；配套应用工程位于 [chromium-desktop-ohos](https://github.com/nimmi114514/chromium-desktop-ohos)。完整 Chromium 源码与第三方依赖按固定版本另行获取。

## 两个仓库如何配合

| 仓库 | 职责 |
| --- | --- |
| [chromium-ohos](https://github.com/nimmi114514/chromium-ohos)（本仓库） | Chromium C++、OHOS 适配层、依赖补丁、原生编译和打包校验 |
| [chromium-desktop-ohos](https://github.com/nimmi114514/chromium-desktop-ohos) | ArkTS 应用壳、系统接口桥接、应用配置和 HAP 工程 |

构建流程为：**固定版本 Chromium 源码 → 应用 OHOS 补丁 → 编译原生库与资源 → 同步至 HAP 工程 → 签名打包**。

内核源码在本地的 `src/` 工作区中编译，Git 提交保存其可重放补丁。`src/` 可以是实际目录或指向独立源码工作区的符号链接，不随本仓库提交。更新设备上的内核需要重新打包并安装 HAP。

## 版本与构建环境

| 项目 | 当前配置 |
| --- | --- |
| Chromium | `158.0.8116.0` |
| 上游固定提交 | `566635fe3ce2912169a6ca76a00a7ee1d8e400e9` |
| 目标 ABI | `arm64-v8a` |
| SDK | API 26，已使用 `26.0.0.105` 构建 |
| 原生工具链 | Chromium 固定版本的 Google Clang 24、Rust 与 libc++ |
| HAP 工具链 | Windows DevEco Studio 26，Hvigor 6.26.8 |
| 当前应用包名 | `com.example.ohos.chromium` |

源码、参考分支和工具链版本记录在 [versions.json](versions.json)，依赖补丁的目标提交记录在 [dependency-patches/series.json](dependency-patches/series.json)。SDK 的 compiler-rt/CRT 来自 API 26 SDK，并非重新编译的 compiler-rt 24。

已完成构建的环境是 Windows + WSL2：Linux 侧编译原生内核，Windows DevEco 工具链打包 HAP。当前自动打包脚本依赖 `wslpath`、Windows PowerShell 和 DevEco 工具路径；其他宿主环境需要调整这部分配置。

## 功能与验证范围

项目仍在适配与回归阶段，当前构建不代表 Chromium 全部功能已经验收。

| 方向 | 当前状态 |
| --- | --- |
| 桌面界面与中文资源 | 已接入桌面界面、横向/纵向标签页及语言资源；此前有设备验证记录 |
| AVC / HEVC 硬件解码 | 已接入 OHOS 解码器，此前验证过实际出帧、跳转和后台恢复；支持范围取决于设备 |
| HDR | 已接入 HEVC PQ/HLG 元数据、10bit EGL 与显示能力；本地样本验证过，网站 HDR 选流和面板绝对亮度/色准尚未完整验收 |
| WebGPU | Vulkan/Dawn 路径此前完成过功能及示例验证；呈现使用暂存拷贝，尚非零拷贝 |
| 填充密码前屏幕锁定认证 | 已恢复入口、中文文案与系统桥接；OHOS 每次受保护填充独立认证；最新修改通过主机模拟回归 |
| 系统截屏 | 已修正受保护媒体结束后窗口隐私状态未释放的路径；最新修改通过主机生命周期检查 |
| DRM | 受保护内容端到端播放尚未完成，不作为当前已支持功能；相关工作暂停 |

当前最新交付记录为 **native107**：原生与 HAP release 构建、235 项原生/资源文件校验、签名校验和补丁重放通过，已安装独立包。该候选未进行安装后的设备功能回归，密码填充和截屏修正尚不作为实机验收结论。

- [native107 交付与验证摘要](reports/native107-delivery.json)
- [密码填充认证回归](reports/native107-password-fill-authentication.json)
- [编译后的中文文案检查](reports/native106-screen-lock-chinese-pack.json)
- [窗口隐私状态生命周期检查](reports/native106-window-privacy-lifecycle.json)
- [开发状态与历史验证范围](STATUS.md)

Graphite、Direct Rendering Display Compositor、TreesInViz、WebNN 当前未启用。受系统权限策略影响，进入 jitless 模式时 WebAssembly 不可用。Google 登录/同步还受凭证、网络与服务端策略影响，不保证可用。历史设备原始日志和账户相关数据不随仓库分发。

JIT：已确认当前设备运行在 jitless，普通 Debug Profile 未包含自带 V8 所需的 ACL；正在按华为官方权限流程接入，尚未通过 JIT 真机验证。参见 [JIT 调查与设备基线](docs/JIT.md)。

## 目录结构

```text
patches/                 Chromium 主仓库补丁及应用顺序
dependency-patches/     V8、Dawn、Skia、ANGLE、FFmpeg 等依赖补丁
hap-patches/             HAP 工程相对原132基线的可重放改动
overlay/                新增构建文件的可读副本
scripts/                 源码获取、补丁、构建、打包与检查工具
references/              132 平台适配参考及调查记录
tests/                   本地回归页面、探针与测试素材
reports/                 已整理的验证摘要；更多报告在本地生成
artifacts/manifest.json  已构建产物的哈希与元数据
src/                     本地 Chromium 源码工作区，不提交
```

## 获取与构建

### 1. 克隆两个仓库

公开仓库名与构建脚本默认的本地目录名不同。以下克隆方式保留脚本默认布局：

```sh
git clone git@github.com:nimmi114514/chromium-ohos.git chromium158-ohos
git clone git@github.com:nimmi114514/chromium-desktop-ohos.git chromium-2in1-hap
cd chromium158-ohos
mkdir -p logs reports artifacts toolchain-resources
```

也可以使用 HTTPS 克隆。已有源码工作区可通过 `src` 符号链接接入。建议将大型源码及编译输出放在 WSL 的 Linux 文件系统中，减少跨文件系统 I/O。

### 2. 准备固定版本源码与工具

需要 Git、Python 3.11+、Chromium Linux 构建依赖、Google depot_tools，以及安装 API 26 SDK 的 Windows DevEco Studio。

将 depot_tools 放入 `PATH` 后，在**首次准备的工作区**执行：

```sh
python3 scripts/sync_chromium.py --mirror --full --deps
python3 src/tools/clang/scripts/update.py
python3 src/tools/rust/update_rust.py
```

`sync_chromium.py` 会获取 [versions.json](versions.json) 指定的源码，并按其 DEPS 同步依赖；脚本使用 `--nohooks`，工具链需要按上面命令另外准备。depot_tools 的已用提交也记录在 `versions.json`。

原生构建脚本还要求 Linux 可执行文件 `tools/gn` 和 `tools/ninja`。请准备这两个工具；已用下载来源与归档哈希见 [GN 记录](tools/gn-download.json)、[Ninja 记录](tools/ninja-download.json)。工具二进制不随仓库提交。

已有移植改动的工作区应先确认当前状态，避免用重新检出源码或同步依赖覆盖正在修改的文件。

### 3. 应用内核和依赖补丁

```sh
python3 scripts/apply_port.py --check
python3 scripts/apply_port.py
```

脚本同时处理主仓库和 `dependency-patches/`，检查目标提交，并识别已经应用的补丁。直接克隆配套 HAP 仓库即可获得应用工程，无需再对它应用 `hap-patches/`；后者用于追溯和重放相对132的改动。

### 4. 导入 SDK 并编译

```sh
python3 scripts/import_deveco_sdk.py \
  --sdk-root "/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default"
python3 scripts/build_native.py --stage chrome --jobs 8 --keep-going 0
```

SDK 路径不同请修改 `--sdk-root`。导入脚本准备 Linux 原生编译所需的 SDK 镜像与资源链接。原生输出目录为 `src/out/OHOS/`，主库为 `libchrome_main_web.so` 和 `libadapter.so`。

### 5. 配置签名并生成 HAP

先在 DevEco Studio 打开同级 `chromium-2in1-hap` 工程，为当前包名配置自己的签名。证书、私钥与密码只保留本地。

```sh
python3 scripts/build_hap.py --stage install
python3 scripts/build_hap.py --stage hap --build-mode release
```

这里 `--stage install` 安装的是 **OHPM 工程依赖**，不会安装应用到设备。`--stage hap` 会先同步本次编译的库与资源，再执行 Hvigor；release 流程还会校验包内容和签名。

使用其他路径时，通过 `--deveco`、`--hap-project` 指定。当前打包校验针对包名 `com.example.ohos.chromium`；更改包名需要同步应用配置与校验规则。

生成位置：

- HAP 工程：`chromium/build/default/outputs/default/chromium-default-signed.hap`
- 本仓库归档：`artifacts/chromium-158.0.8116.0-ohos-api26-arm64-release-signed.hap`
- 产物记录：[artifacts/manifest.json](artifacts/manifest.json)

原生库、运行资源、SDK、工具二进制、HAP 和个人签名文件不进入源码提交。仓库中的 manifest 是已有构建的记录，不表示仓库中附带安装包。

## 修改后导出补丁

在 `src/` 修改源码并完成相应检查后，导出可重放补丁：

```sh
python3 scripts/export_port.py
```

脚本核对固定版本，导出主仓库与依赖改动，并在原始 Git 文件上重放比较。需将更新后的补丁一同提交到本仓库；HAP 源码改动另外提交到配套应用仓库。

## 来源与致谢

本项目沿用并参考成熟的 Chromium 132 OHOS 移植工作，将相应平台实现适配到 Chromium 158：

- [Chromium 项目](https://chromium.googlesource.com/chromium/src/)及其第三方依赖：浏览器内核与基础组件。
- [OpenHarmony-TPC Chromium 移植项目](https://github.com/OpenHarmony-TPC/chromium_src)：`pc_chromium_132` 平台实现及相关工具链参考；所用参考提交见 `versions.json`。
- [Nyaacho0v0/chromium-2in1-hap](https://github.com/Nyaacho0v0/chromium-2in1-hap)：原132 HAP 应用工程，是配套158应用工程继续开发的基础。
- 所沿用源码中署名的 Haitai FangYuan 等贡献者，以及各上游项目的维护者。

沿用文件中的原始版权和许可声明保留；Chromium 与第三方组件各自的许可信息随其上游源码提供。
