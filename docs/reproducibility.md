# 构建可复现性核查

## 源码组成

两个对外仓库保存应用外壳与全部移植补丁。Chromium基线、depot_tools与配套HAP源码提交记录在versions.json，九个修改依赖的基线及补丁哈希记录在dependency-patches/series.json。

主仓库补丁覆盖1906个移植文件；第三方未修改依赖按固定Chromium的DEPS下载，修改依赖在下载后应用补丁。
无需私有子仓库或本地未公开的产品源文件。`git submodule update`不能下载DEPS中的CIPD/GCS包，必须使用README给出的gclient步骤。

## 本次修补的构建缺口

- 增加固定depot_tools获取脚本，禁用自动滚动版本。
- 增加prepare_build.py，从DEPS下载结果准备GN/Ninja及必需的LASTCHANGE、MINIBRANCH、GPU/Skia/Dawn头文件。
- 保留SDK运行资源overlay的生成流程，自动创建首次构建所需的报告目录。
- build_native.py可接受基于固定上游的本地commit，仍校验真实Chromium版本；默认V8日志级别与当前交付一致。
- 补齐全新工作区、系统依赖、签名与HAP步骤，删除过时JIT状态及不存在的文档链接。

## 验证记录

本轮正在独立目录进行干净基线加补丁、工具准备及GN构建图验证。完成后更新本节。
验证过程中可复用固定上游的本机对象/下载缓存，但不复用已修改的九组依赖源码或旧GN输出。

## 外部前提与边界

API26 SDK、Windows DevEco与自己的HarmonyOS签名需从官方渠道自行准备，不能把作者个人签名上传仓库。
所有源代码完整与任意设备上JIT/DRM/硬解授权可用是不同条件；固件和签名权限不由源代码仓库代替。
不同签名、构建路径、时间及工具细节可能导致HAP哈希不同，本项目不承诺逐字节可复现。
