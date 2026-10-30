# Chromium for OHOS

将 **Chromium 158.0.8116.0** 移植到 **OHOS / HarmonyOS arm64** 的社区项目，面向平板与 2in1 设备，当前使用 **API 26** SDK 构建。

本仓库保存内核及依赖的适配补丁、构建工具和验证记录；配套应用工程位于 [chromium-desktop-ohos](https://github.com/nimmi114514/chromium-desktop-ohos)。完整 Chromium 源码与第三方依赖按固定版本另行获取。

当前本地交付与修复范围见 [2026-10-28交付记录](docs/delivery-2026-10-28.md)。

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
| USB HID / WebHID | 已加入 OHOS USB HID 枚举、授权、报告描述符及输入/输出报告通道 |
| AVC / HEVC 硬件解码 | 已接入 OHOS 解码器，此前验证过实际出帧、跳转和后台恢复；支持范围取决于设备 |
| HDR | 已接入 HEVC PQ/HLG 元数据、10bit EGL 与显示能力；本地样本验证过，网站 HDR 选流和面板绝对亮度/色准尚未完整验收 |
| WebGPU | Vulkan/Dawn 路径此前完成过功能及示例验证；呈现使用暂存拷贝，尚非零拷贝 |
| 填充密码前屏幕锁定认证 | 已恢复入口、中文文案与系统桥接；OHOS 每次受保护填充独立认证；最新修改通过主机模拟回归 |
| 系统截屏 | 已修正受保护媒体结束后窗口隐私状态未释放的路径；最新修改通过主机生命周期检查 |
| DRM | 受保护内容端到端播放尚未完成，不作为当前已支持功能；相关工作暂停 |

当前交付包含 **2026-10-28 原生历史/书签弹窗与新增收藏生命周期修复**，并包含OHOS V8内嵌builtins复制回退。用户反馈本次问题已正常，范围与限制见[交付记录](docs/delivery-2026-10-28.md)及[开发状态](STATUS.md)。应用版本为 `1.0.1`，Chromium内核版本单独记录为 `158.0.8116.0`。

JIT保留132的系统权限与安全模式门控；满足条件时使用V8 JIT，OHOS启动路径跳过内嵌builtins页重映射优化。未引入JITFort依赖，也不承诺任意固件、签名或系统安全配置下均可启用JIT。

Graphite、Direct Rendering Display Compositor、TreesInViz、WebNN当前未启用。DRM工作暂停，Widevine与会员网站受保护内容播放不是已实现功能。Google登录/同步受凭证、网络与服务端策略影响，不保证可用。

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

## 从两个仓库构建完整 HAP

源码改动由本仓库的10个主补丁和9组依赖补丁完整保存，HAP源码由配套仓库保存。
V8、Dawn、Skia等上游依赖通过Chromium固定版本的 **DEPS / gclient** 获取，再应用这里的补丁；无需另建或私下获取作者的子仓库，也不是仅克隆这两个小仓库便已经下载了完整Chromium。

以下流程面向 **Windows + WSL2 Linux x86_64**。需要自行安装：

- Windows DevEco Studio 26，SDK Manager中安装API26；本项目已使用SDK `26.0.0.105`、Hvigor `6.26.8`。
- WSL2 Ubuntu，Git、Python 3.11+、编译宿主依赖。不要在Windows Python里执行原生构建脚本。
- 能访问GitHub、chromium.googlesource.com、Google CIPD/GCS与OHPM的软件源。源码与预编译工具体量较大，首次同步耗时取决于网络。
- 建议为源码/依赖/构建输出预留150GB以上空间，RAM 16GB以上；内存较小时减少 `--jobs`。
- 自己的HarmonyOS签名证书/Profile。SDK和个人签名材料不随仓库提供，源码完整不等于可以复用作者的设备签名。

### 1. 克隆项目并建立源码目录

在WSL执行。HAP工程放Windows盘便于DevEco打开，大型内核工作区放WSL的Linux文件系统：

```sh
mkdir -p /mnt/d/chromium
cd /mnt/d/chromium
git clone https://github.com/nimmi114514/chromium-ohos.git chromium158-ohos
git clone https://github.com/nimmi114514/chromium-desktop-ohos.git chromium-2in1-hap
cd chromium158-ohos
mkdir -p logs reports artifacts toolchain-resources
mkdir -p "$HOME/chromium-build/158.0.8116.0"
ln -s "$HOME/chromium-build/158.0.8116.0/src" src
```

上面的 `ln -s` 只用于首次准备；不要覆盖已有 `src` 或已有源码改动。D盘路径可以自行调整，两项目建议保持同级，后续命令均在内核适配仓库运行。

### 2. 获取固定版本源码、全部依赖和构建工具

```sh
python3 scripts/bootstrap_depot_tools.py
export PATH="$PWD/tools/depot_tools:$PATH"
export DEPOT_TOOLS_UPDATE=0
python3 scripts/sync_chromium.py --mirror --full --deps
```

脚本使用 `versions.json` 固定Chromium和depot_tools版本；`gclient sync --nohooks`按该Chromium的DEPS下载Git依赖及CIPD/GCS包，包含Clang、Rust、Node、TypeScript、宿主sysroot、GN和Ninja。
**不能用 `git submodule update` 代替gclient**：后者还负责非Git工具包及生成gclient配置。

安装Chromium的Linux宿主依赖（会请求sudo并安装系统软件包），然后补齐跳过hooks时必需的版本文件与工具入口：

```sh
bash src/build/install-build-deps.sh --no-prompt
python3 scripts/prepare_build.py
```

`prepare_build.py`检查必需工具，将DEPS固定版本的GN/Ninja链接到 `tools/`，并生成LASTCHANGE、MINIBRANCH、GPU/Skia/Dawn版本头文件；无需手工找工具二进制，也不使用不断变化的GN `latest`。
这条最小流程不需要下载性能测试数据的全部hooks。正常gclient同步已经取得固定Clang/Rust，无需额外运行会改变工具链的更新命令。

### 3. 应用内核与依赖补丁

```sh
python3 scripts/apply_port.py --check
python3 scripts/apply_port.py
```

补丁基线固定为 `566635fe3ce2912169a6ca76a00a7ee1d8e400e9`，依赖基线见 `dependency-patches/series.json`。
检查不通过应停止，不要跳过失败的补丁继续编译。已完整应用时脚本会识别并跳过。
**应用补丁后不要再次执行gclient sync覆盖依赖改动**；日常增量编译从第4步继续。
直接克隆HAP仓库即可获得应用源码，不需要再对它应用 `hap-patches/`（后者仅作132改动追溯）。

### 4. 导入API26 SDK并编译原生内核

```sh
python3 scripts/import_deveco_sdk.py \
  --sdk-root "/mnt/c/Program Files/Huawei/DevEco Studio/sdk/default"
python3 scripts/build_native.py --stage chrome --jobs 4 --keep-going 1
```

DevEco安装路径不同需修改 `--sdk-root`。导入脚本只复制交叉编译目标文件并准备Clang资源overlay；实际编译器使用Linux版Google Clang，不执行Windows SDK的编译器。
原生输出为 `src/out/OHOS/`，包含 `libchrome_main_web.so`、`libadapter.so`、ICU、语言PAK和V8快照。
构建脚本生成当前release配置：官方构建、无DCHECK调试配置、H.264/AAC媒体配置，以及保留V8 fatal日志的 `v8_logging_level=1`。

仅检查GN构建图可使用：

```sh
python3 scripts/build_native.py --stage chrome --generate-only
```

首次原生编译工作量大；中断后重新运行同一编译命令可增量继续。遇到OOM请减少 `--jobs`，不要通过删除平台补丁解决。

### 5. 配置本机签名

Windows DevEco Studio打开 `D:\chromium\chromium-2in1-hap`，同步工程依赖，在Project Structure → Signing Configs为当前包名 `com.example.ohos.chromium` 配置自己的签名。
仓库中的 `build-profile.json5` 为无签名模板；本机生成的签名配置、证书路径、私钥、密码不要提交。
可以在本地签名前执行以下命令，使该模板的本机签名修改不进入普通Git状态列表：

```sh
git -C ../chromium-2in1-hap update-index --skip-worktree build-profile.json5
```

此标志不是加密，仍须自行保管签名材料；需要升级模板时先备份本机签名配置，再使用 `--no-skip-worktree` 恢复跟踪。
JIT是否实际可用由设备固件、系统安全模式和有效授权决定；仓库不提供虚构权限、JITFort绕过或他人的签名文件。

### 6. 编译、校验与安装HAP

```sh
python3 scripts/build_hap.py --stage install
python3 scripts/build_hap.py --stage hap --build-mode release
```

`--stage install`安装的是OHPM工程依赖，不会安装应用到设备。
`--stage hap`先同步刚编译的原生库和运行资源，再调用Windows Hvigor；release完成后核对库的实际ELF内容、语言资源、快照、WebUI资源及HAP签名。
使用不同目录时追加 `--deveco`、`--hap-project`；打包工具必须能从Windows访问HAP工程，推荐放在 `/mnt/d/` 等Windows盘路径。

生成位置：

- HAP工程：`../chromium-2in1-hap/chromium/build/default/outputs/default/chromium-default-signed.hap`
- 本仓库归档：`artifacts/chromium-158.0.8116.0-ohos-api26-arm64-release-signed.hap`
- 本次产物清单：`artifacts/manifest.json`（由每次构建重新生成，历史清单不是附带安装包）。

在Windows终端使用DevEco SDK的hdc覆盖安装：

```sh
hdc install -r chromium-2in1-hap/chromium/build/default/outputs/default/chromium-default-signed.hap
hdc shell aa start -b com.example.ohos.chromium -a EntryAbility
```

覆盖升级还需签名身份一致；使用自己的签名不能直接覆盖另一开发者签名的安装包。不要为排障默认删除用户Profile。

### 可复现范围

目标是从固定源码和补丁构建相同功能的Chromium 158 OHOS。不同机器的绝对路径、构建时间、签名证书和工具细节会影响二进制或HAP哈希，不承诺与作者HAP逐字节相同。
本仓库不包含私有源码依赖；标准Chromium依赖按DEPS获取，平台适配代码以可重放补丁提供。
具体已执行检查及未执行部分见 [构建可复现性核查](docs/reproducibility.md)。

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
