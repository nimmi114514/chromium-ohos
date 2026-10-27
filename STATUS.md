# Chromium158 / OHOS API26

## 当前：native107 密码填充认证与截图隐私状态修正

2026-10-26。包名为 `com.example.chromium`，不覆盖132。

- native105的屏幕锁定开关缺少settings-private偏好读取白名单，造成认证成功后界面
  无法跟随状态；native106已补回读取与通知，保留只读限制，修改仍经过系统认证。
- 恢复132原有文案，编译出的zh-CN资源已核对，开关显示“填充密码时使用屏幕锁定”。
- 用户随后反馈刚开启后填充不弹认证。原有132逻辑共享每个Profile的成功认证时间，
  填充允许复用60秒内的认证。native107将OHOS填充有效期设为0，每次填充独立认证；
  保留132的鸿蒙认证桥接，并补回自动填充、手动填充、HTTP认证与Credential API用途文案。
- PIN、指纹/人脸认证仅在系统返回SUCCESS时成功，取消、失败和未录入均阻止填充。
- 原截图黑屏路径把加密媒体标记永久OR为true。现按播放器与WebContents跟踪隐私状态，
  释放最后一个受保护播放器后清除对应窗口标记；同窗口其他受保护内容仍受保护。

主机检查：ArkTS认证桥接8项、实际C++隐私方法8项、认证缓存/填充7项通过；
认证检查执行实际生产方法，能复现旧60秒跳过认证，并验证0秒时立即和连续填充
均调用模拟系统认证，失败不填充。系统API为模拟，不等同实机指纹验证。
原生与HAP构建、资源和签名校验及补丁重放记录见交付报告。
按用户要求，安装后不启动应用、不进行设备回归，不声明截图或实际填充已真机验收。

DRM工作停止；菜单尺寸保持不动；Google社区凭证配置保持原样。
签名证书、私钥和密码只保留本地，不提交，不推送或发布Release。

证据：[本次交付](reports/native107-delivery.json)、
[认证缓存与填充检查](reports/native107-password-fill-authentication.json)、
[编译中文资源](reports/native106-screen-lock-chinese-pack.json)、
[窗口隐私生命周期检查](reports/native106-window-privacy-lifecycle.json)。

## 以下为历史记录（不代表当前候选已经完成同样的设备验证）


2026-10-26：用户要求先放弃DRM，相关任务已停止。当前安装native104诊断包；测试目标已关闭，临时HDC映射已清理，HAP源码已移除临时CDP参数（未重新编译安装）。未解决的AAC缺钥后seek问题与修改记录保留，不能视为DRM完成。详见reports/drm-work-stopped.json。

更新：2026-10-26。当前安装为native102 WisePlay诊断包，包含临时localhost CDP参数，不是DRM已完成的最终交付。native097是此前清理调试参数的归档。Widevine原生实测不可用；WisePlay会话已验证，加密音视频完整播放未通过。本轮按要求转为官方示例审计，停止试改和编译安装。
独立包名 `com.example.chromium`，132 应用未改动。以下native073以前记录为历史验证，HDR本轮见文末。

本轮硬解修正：明确初始化 DRM 等待状态；撤回本轮引入、造成 EGL 跨线程失败的
OHOS DrDc 默认启用；为 158 新的 Canvas 视频读取接口补齐共享纹理 RasterRead 用途。
保留 132 的解码器桥接、回调和 NativeImage 流程；GPU 光栅化继续启用。

已验证：AVC、HEVC 使用 OHOSVideoDecoder 输出实际画面；连续播放、Canvas 像素读取、
进度跳转恢复通过。1080p AVC 连续播放和跳转通过。
HEVC 实测累计播放 150 秒、后台等待 120 秒，3911 帧、7 帧丢失，恢复正常，
观察窗口没有新增 cppcrash/jscrash；用户反馈后台崩溃未再出现。
后台期间断开页面调试的额外对照也通过：150 秒、4500 帧、零丢帧，页面未被丢弃。
未修改 Chromium 性能设置；最终包安装后 180 秒观察通过，无新增 cppcrash/jscrash。

设备能力查询：AVC、HEVC 暴露硬件解码器；AV1、VP8、VP9 未暴露硬件解码器。
未查证“专利导致 AV1 缺少硬解”的官方证据。此前公开视频已验证 Dav1d AV1 软解可播放。

当前最终包上生成页面的 DOM、Canvas、WebGL 九组测量完整结束。
测试页面窗口及原生菜单静止底边未捕获到蓝色像素；实际拖拽、扩展弹窗尚未完成验证。
用户反馈测试页反复抢前台，已停止前台测试循环、服务及临时反向端口。
为避免打断当前其他应用，未强行切回 Chromium 关闭剩余测试标签页；待安全清理。
不能据此判定蓝边全部消失。
完整功能回归未全部完成，不能把本轮媒体测试视为全部功能验收。

证据：

- [本轮修正与回归](reports/native072-hardware-and-background-fix.json)
- [AVC 画面读取与跳转](reports/native072-h264-readback-and-seek.json)
- [HEVC 后台 120 秒回归](reports/native072-hevc-background-120.json)
- [设备硬解能力查询](reports/native067-device-codec-capabilities.json)
- [最终包运行文件一致性](reports/native073-tested-runtime-parity.json)

以下是此前 native059–061 闪退修复记录，不代表当前硬解已验收：

本次优先修复两类已确认的闪退：

- cppcrash：音频回调由132的std::shared_ptr注册表管理，却同时继承侵入式引用计数。
  去掉未使用的引用计数继承，保留注册表、回调分发、锁和Detach流程。
- jscrash：设备保存的5次记录均指向缺失的UpdateDisplayBrightnessCB。
  只有原生接口可用时才注册亮度观察者，窗口销毁时清理，并防止迟到回调。

验证：合并版40次音频上下文开关、8次实际原生渲染器释放通过；每批等待7秒，
关闭测试页后等待15秒。合并版观察240秒，无新增cppcrash/jscrash。
去掉临时调试参数后重新签名安装，原生和运行资源与测试版本相同；
再观察180秒，进程持续存活，两类崩溃记录均为空。
实际ArkTS方法的缺失接口、正常回调、接口变化、迟到回调、重复清理测试通过。

标签栏保留用户确认正确的native053实现，基线保存于
`artifacts/history/native053-tabs-confirmed/`。
此前修正仍保留：73个设置页面渲染无脚本异常；无MDM时管理状态为false；
管理页和discards页补回34项PAK资源；打包校验覆盖9个页面的138项资源。
HTTPS、下载、PDF、书签操作、WebGL和存储等已有单项测试证据。

完整功能回归尚未全部完成。按132权限策略进入jitless时WebAssembly不可用；
原生输入法、剪贴板、打印等仍未全面验证。不能把本轮崩溃回归视为所有功能验收通过。

证据：

- [当前构建状态](reports/api26-build-completion.json)
- [音频cppcrash修正](reports/native059-audio-cppcrash.json)
- [亮度jscrash修正](reports/native060-brightness-jscrash.json)
- [实际音频释放压力测试](reports/native060-audio-lifecycle.json)
- [合并版240秒观察](reports/api26-device-startup-native060-audio-and-brightness.json)
- [最终包180秒观察](reports/api26-device-startup-native061-final-crash-fix.json)
- [最终包与测试版运行资源一致](reports/native061-tested-runtime-parity.json)
- [73个设置页面检查](reports/native058-settings-audit.json)

原生工程：`D:\chromium\chromium158-ohos`。
ArkTS/HAP工程：`D:\chromium\chromium-2in1-hap`，DevEco显示名称为chromium-hap。
本机签名私密配置未导出。

## native074：纵向标签页窗口按钮避让

OHOS 避让高度原来只取横向标签栏高度，纵向时变成 0，导致整个区域被忽略。
改为使用158的顶部元素总高度：横向仍为标签栏，纵向为工具栏；132读取原生按钮宽度的逻辑保留。
已编译、签名、安装独立158包。设备纵向布局工具栏右边界2662，系统按钮区域左边界2726，相隔64像素；用户确认问题解决。
180秒记录没有新增cppcrash/jscrash，期间PID变化，因此不声称进程连续存活。
当前转向检查HDR显示能力、解码及输出链路；尚未声称支持HDR。
证据：[修正和设备几何](reports/native074-caption-fix.json)。

## HDR：native083 本地通路验证

已实现 HEVC PQ/HLG 帧色彩和静态元数据传递、显示 HDR/P3 能力与亮度信息桥接、
NativeWindow 色彩空间与 HDR 类型设置、10/10/10/2 EGL 输出以及 HDR/SDR 切换。
SDR 继续使用原132 NativeImage 路径；没有强行提升系统亮度。

native082 的五项生成媒体回归通过：HEVC Main10 PQ、HLG、彩色色条、10bit渐变、AVC SDR；
均有实际出帧、读取和跳转验证。色条与同一编码样本的CPU解码参考最大误差1/255，
10bit渐变读回超过512个不同灰阶。HDR样本最小化30秒后恢复出帧。
样本无音轨，后台被正常暂停；本项不声称持续后台播放。

实机诊断观测到解码器NativeImage缓冲格式P010（35），EGL输出10/10/10/2，
系统当前HDR headroom从1升至约5。未用亮度计/色度计测量面板，不能声称绝对亮度和面板色准已校准。
匿名YouTube测试被Google异常流量验证页阻断，尚未取得HDR视频流；哔哩哔哩HDR选流也未验收。

原作者HAP仓库README与v1.0.0 Release明确宣称132支持10bit HDR。
先前比较的pc_chromium_132上游原生基线不能代表作者定制二进制的全部能力。
原始调查报告已补充这一范围纠正。

native083已编译签名并通过235项原生/运行资源和签名校验，原生build ID与测试候选相同。
最终包只保留HDR开关，临时CDP参数和原生buffer/config探针已移除。
原生10个补丁、依赖9个补丁及HAP17个补丁均可重放。
最终包安装后180秒PID 34285持续存活，没有新增cppcrash/jscrash。此项不能覆盖用户随后报告的网页IPC拒绝终止。
正在定位Apple Music RESULT_CODE_KILLED_BAD_MESSAGE。

证据：

- [五项回归与最小化恢复](reports/native082-hdr-final-regression.json)
- [P010实际缓冲证据](reports/native081-input-bit-depth.json)
- [HDR亮度/色彩验证范围](reports/native081-hdr-validation-summary.json)
- [最终原生库一致性](reports/native083-tested-native-parity.json)
- [凭证保持原样的核对](reports/native083-credential-config-parity.json)

## Google凭证审计

用户决定保持现有配置。三个值与原始132公开源码相同，最终HAP中也存在。
原作者注释称其为社区公开值；归属和额外分发授权未独立确认。
公开可见不能视为第三方分发授权，Google浏览器登录/同步还有服务端限制。
本轮没有修改凭证、账号配置或发布仓库/Release。
证据：[原始仓库审计](reports/original132-google-credential-audit.json)。

## native086：Apple Music RESULT_CODE_KILLED_BAD_MESSAGE

已匿名复现：未登录时打开约5秒即收到
`No binder found for interface media.mojom.KeySystemSupport for the frame/document scope`，bad IPC reason 123。
132已在frame binder注册条件中包含ENABLE_WISEPLAY；158遗漏，现已补齐，并添加显式头文件与GN依赖。
没有关闭IPC消息校验。

设备验证：12次EME能力查询正常返回；Apple Music页面和登录表单60秒存活，0脚本异常，
140秒捕获0条IPC拒绝。最终包去掉CDP后签名安装，180秒主进程持续存活，无新增cppcrash/jscrash；
额外100秒IPC捕获也为空。会员歌曲的受保护DRM播放未验证，当前Widevine AAC配置返回NotSupportedError。
HDR回归中PQ/HLG/彩条/渐变通过；最后AVC时调试会话消失，重跑渐变和AVC均通过。
该中断原因未确定，没有新增设备cpp/js记录，不计为单次完整五项连续回归通过。

证据：[根因和验证](reports/native085-apple-music-root-cause.json)。

## WebGPU：native089 功能验证

用户已要求实施WebGPU。native086稳定HAP已归档至artifacts/history/native086-before-webgpu。
native087临时驱动探针在应用进程内确认Maleoon935支持Vulkan1.3.309、Dawn基础特性、ETC2/ASTC，
以及外部内存/同步FD。GLES缺少桌面GL外部内存扩展，首轮采用Chromium现有Skia暂存拷贝桥接显示；
shader仍在Vulkan GPU执行。普通网页保留Ganesh/GLES路径，不启用Graphite/DrDc/TreesInViz/WebNN。
native089实机13项功能验证及3个官方示例通过：计算、Canvas呈现、纹理复制、透明度、视频外部纹理、Worker和设备生命周期。
官方示例通过本机镜像加载，不能视为远程站点HTTPS访问已通过。Vulkan执行shader，显示使用暂存拷贝，非零拷贝。
报告：reports/native089-webgpu-video-functional.json、reports/native089-webgpu-samples-mirror.json。
凭证配置保持原样。

## DRM：native090–093

恢复132已有、158启动流程遗漏的WisePlay CDM注册和DRM桥接客户端初始化，覆盖进程内和独立GPU。
修正安全解码能力查询误把isEncoder参数当作isSecure的问题，按设备实际安全硬件解码器查询。
初始化SDK许可证请求结构，响应处理传入真实缓冲区容量；先通知会话关闭再完成close()，避免158释放监听后session.closed永久等待。
实机普通窗口WisePlay AAC/AVC/HEVC能力查询通过；无痕窗口按现有策略不暴露WisePlay。
连续三轮会话创建、许可证请求、无效许可证拒绝、关闭通知、重复关闭、关闭后更新拒绝通过。
诊断包启动120秒PID持续存活，无新增cppcrash/jscrash；120秒IPC拒绝捕获为空。

该设备DRM服务只列出com.wiseplay.drm。Widevine/PlayReady/FairPlay仍无可用系统插件或授权CDM，未伪装支持。
EZDRM官方公开示例许可证端点返回404；华为旧公开示例端点TLS连接失败。未取得有效许可证，受保护内容解密和播放仍未验收，
不能把能力查询和会话测试通过写成会员网站可播放。许可证请求/响应内容未记录，Google凭证未修改，132包未改动。
证据：reports/native093-drm-fixes.json、reports/native093-drm-session-verified.json、reports/native093-drm-ipc-rejections.json。

## Widevine：native096 原生能力实测

用户明确要求Widevine，WisePlay修复不构成该任务完成。
已在独立158应用内直接调用原生DRMKit，绕过Chromium EME和ENABLE_WIDEVINE编译开关：
系统插件枚举只有com.wiseplay.drm；com.widevine.alpha及标准UUID的两种写法均不支持，
AVC/HEVC/AAC查询均false，创建Widevine实例均失败（通用服务错误24700201）。
同一探针WisePlay查询和创建成功，并正常销毁，作为正对照。未请求证书、许可证或记录相关内容。
此证据说明当前固件未向本应用暴露可用的Widevine实例，不能据此推定具体商业拒绝原因或所有鸿蒙设备的状态。
普通Linux ARM64 library CDM的上游平台门控不含OHOS；当前无已授权且兼容OHOS的CDM/SDK可用于实际加载与播放验证。
Widevine仍未实现，待可用系统插件或授权兼容组件。临时探针已从应用源码移除，源代码仅留tests/drm/WidevineProbe.ets复查。
证据：reports/native096-widevine-native-capability.json。

native097已恢复干净应用源码，编译后的ArkTS字节与native094完全一致；原生库build ID一致。临时CDP端口已移除，Google配置未改。最终安装观察见reports/api26-device-startup-native097-clean-after-widevine-probe.json。

## WisePlay后续验证：native098–100

实际许可证请求按HMS-Core官方HttpMediaDrmCallback改用application/json复测，公开EZDRM端点仍返回404；
华为旧公开示例端点在WSL代理、直连与Windows请求中均无法完成TLS连接。受保护播放仍无有效许可证可验收。
通过实际加密媒体加载发现132移植遗漏：MojoVideoDecoder、MojoAudioDecoder的SupportsDecryption白名单缺少ENABLE_WISEPLAY。
native099按132补回条件后，视频不再初始化拒绝，能够播放片源的明文引导段，在约9.78秒触发waitingforkey并稳定停止推进。
测试样本第0视频片段明文10秒、音频片段明文6.016秒，后续片段具有senc；不能把引导段播放算作DRM解密成功。
单独AAC测试进入OhosAudioDecoder，但未正确等待缺失密钥；native100补齐整帧加密长度后仍失败。native101确认解密配置成功且有加密样本输入；native102增加异步错误等待处理仍未通过，未观测到该错误回调。没有有效许可证，不能声称已解密播放。
测试工具已修正后台延迟加载、双轨SourceBuffer创建顺序和明文引导段判断。
证据：reports/native099-wiseplay-decoder-fix.json、reports/native099-wiseplay-encrypted-fragments.json、reports/native100-wiseplay-aac-fix.json。

## WisePlay官方示例审计（停止试改）

已固定下载华为HMS WisePlay示例、OpenHarmony MediaCollections及Native DRM/AVCodec官方指南，并对照许可证、CENC、调用顺序和事件处理。确认当前原生音频主调用顺序与指南相符；许可证就绪协调、KEY_REQUIRED/KEY_EXPIRED处理及部分API返回值传播仍有明确审计缺口。没有将这些缺口冒充已证实的AAC异常根因，本轮未修改原生代码或安装。

详细差异及后续验证顺序：[官方示例审计](reports/wiseplay-official-example-audit.md)。原始来源、固定提交与校验值：references/wiseplay-official/sources.json。
