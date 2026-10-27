# Electron鸿蒙化指导文档

[TOC]

> Note：如果您在其他平台未使用过此框架，不建议您直接使用该框架。您可以从自身软件跨平台演进整体规划上对跨平台框架进行选择。

## API 文档

完整的 OHOS API 文档，请参阅 [API 文档入口](./docs/api/README.md)。

- [全量 API 索引](./docs/api/index.md) - 共 1294 个 API
- [按模块浏览](./docs/api/README.md#按模块浏览) - 66 个模块

## 环境配置

操作系统：Ubuntu 22.04

磁盘空间：大于200G

内存：大于32G

CPU架构：x86_64

## 编译源码构建应用
### 源码与工具下载安装

#### 工具安装

1. 代码仓库网址

[master](https://gitcode.com/openharmony-sig/electron/tree/master)


2. 安装工具`git-lfs`, `ccache` 。**注：该步骤仅在首次拉取代码时需要执行**

   ```sh
   # 安装 git-lfs，确保仓库中的大文件能拉取到本地。ccache 为编译器缓存。
   $ sudo apt install git-lfs ccache
   ```

![7](./res/1.png)

3. 配置工具`repo` 。**注：该步骤仅在首次拉取代码时需要执行，执行该步骤前请确保已经配置好了python3环境**

   ```sh
   # 下载码云repo工具(可以参考码云帮助中心：https://gitee.com/help/articles/4316)
   $ mkdir -p ~/bin
   $ curl https://gitee.com/oschina/repo/raw/fork_flow/repo-py3 > ~/bin/repo
   $ chmod a+x ~/bin/repo
   $ echo 'export PATH=~/bin/:$PATH' >> ~/.bashrc
   $ source ~/.bashrc
   $ pip install -i https://pypi.tuna.tsinghua.edu.cn/simple requests
   ```

#### 安装nodejs环境

可选三种方式安装：

##### 通过Ubuntu标准软件库

此方式安装的node需要单独安装npm

```
sudo apt update
sudo apt install -y nodejs npm
```

查看版本号

```
node -v
```

##### 通过NodeSource仓库安装

通过该方式安装的nodejs同时包含了node和npm，npm无需单独安装

```
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

查看版本号

```
node -v
npm -v
```

##### 通过nvm安装

```
git clone https://gitee.com/mirrors/nvm
cd nvm
bash install.sh
source ~/.bashrc
```

查看nvm版本号并安装nodejs

```
nvm -v
```

安装nodejs（版本20.18.1，32位或64位，下面以32位为例），使用并查看版本号

```
nvm install node 20.18.1 32
nvm use 20.18.1
node -v
```



#### 拉取chromium-electron仓库代码

1. 从代码仓克隆chromium-electron仓库。

   ```sh
   # 使用https拉取chromium-electron代码
   $ git clone -b master https://gitcode.com/openharmony-sig/electron.git
   $ cd electron   # 切换到刚刚拉取的electron仓库目录
   
   $ git lfs pull  # 执行命令`git lfs pull`，确保仓库中的大文件已经下载完成
   
   # 拉取chromium-electron对应的ohos chromium代码
   $ repo init -u  https://gitcode.com/openharmony-tpc/manifest.git -b pc_chromium_132 -m chromium.xml --no-repo-verify
   $ repo sync -c  # 可以执行多次，以确保代码全部拉取成功
   $ repo forall -c 'git lfs pull'  # 可执行多次，以确保大文件全部拉取成功
   
   # 应用chromium-electron的patch到ohos chromium
   $ pushd src
   $ find -name "*.git*" -exec rm -rf "{}" \;
   $ popd
   $ chmod +x override_files.sh
   $ ./override_files.sh
   ```
   
2. 运行 Electron实际目录/src/build/install-build-deps.sh脚本，安装编译所需的软件包。**注：该步骤仅在首次拉取代码时需要执行**

   ```sh
   $ sudo ./src/build/install-build-deps.sh --no-chromeos-fonts
   ```

   ![10](./res/6.png)

3. 运行脚本`electron_build.sh`。

```sh
$ ./electron_build.sh
```

#### Q&A：Electron 编译报错处理

**Q：执行 `./electron_build.sh` 进行编译时，为什么会出现如下报错？** 
`cannot access 'rust-toolchain.tar.gz' : No such file or directory`

**A：** 因为在执行 `./override_files.sh` 时，网络不稳定导致拉取 `rust-toolchain.tar.gz` 未成功。

### 输出结果

编译完成后，会在src/out/musl_64目录下输出的编译产物文件如下：

> locales/
> libelectron.so
> electron
> resources.pak 
> chrome_100_percent.pak
> chrome_200_percent.pak
> icudtl.dat 
> libadapter.so
> libffmpeg.so
> v8_context_snapshot.bin

可以通过如下脚本拷贝所需资源(注：请参考修改为自己的source_path)

```sh
#!/bin/sh
source_path=./Electron实际目录/src/out/musl_64
destination_path=./electron
if [ -d ${destination_path} ];then
	rm -rf ${destination_path}
fi
mkdir ${destination_path}
cp ${source_path}/libelectron.so ${destination_path}
cp ${source_path}/libffmpeg.so ${destination_path}
cp ${source_path}/libadapter.so ${destination_path}
cp ${source_path}/electron ${destination_path}
cp ${source_path}/icudtl.dat ${destination_path}
cp ${source_path}/v8_context_snapshot.bin ${destination_path}
cp ${source_path}/chrome_100_percent.pak ${destination_path}
cp ${source_path}/chrome_200_percent.pak ${destination_path}
cp ${source_path}/resources.pak ${destination_path}
mkdir ${destination_path}/locales
cp ${source_path}/locales/zh-CN.pak ${destination_path}/locales
cp ${source_path}/locales/en-US.pak ${destination_path}/locales
```

将脚本保存为copy.sh放置于编译文件夹chromium文件夹同级，并执行，执行脚本后会将所需资源拷贝到同级的electron中。



## hap包构建与使用
hap包工程位置：源码目录src/ohos/app/文件夹内。

### 编译未签名的hap包

在工程中新建**electron/libs/arm64-v8a**文件夹，替换**electron/libs/arm64-v8a**目录与**web_engine/src/main/resources/resfile**目录下的资源，并使用DevEco Studio进行编译安装。

**libc++_shared.so**需要从**/src/ohos_sdk/openharmony/native/llvm/lib/aarch64-linux-ohos**下拿取，上述文件在sdk压缩包解压后出现。

将electron工程源码（若需要编译则需将编译产物）放置到**web_engine/src/main/resources/resfile/resources/app**目录下。

![13](./res/9.png)

上图中所需要的resfile/resources/app目录下测试文件可在chromium-electron仓resources目录下找到
so库与resfile都放入指定位置后，点击 **Build -> Build Hap(s)/APP(s) -> Build Hap(s)** 按钮编译生成未签名的hap包或点击**右上角运行按钮**启动应用。

![14](./res/10.png)

![15](./res/10-2.png)

编译完成后，未签名的hap包会被保存到**ohos_hap/electron/build/default/outputs/default/**下，文件名**electron-default-unsigned.hap**。

![16](./res/11.png)

### 签名与权限  

[应用/服务签名-DevEco Studio - 华为HarmonyOS开发者 (huawei.com)](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-signing#section18815157237)

权限申请邮件内容示例如下：

**请根据实际需要的授权申请权限，示例内容仅供参考**

![17](./res/15.png)

权限配置文件位置：**ohos_hap\web_engine\src\main\module.json5**文件中**requestPermissions**字段，以下是当前声明的权限及说明。

| 权限名                                                | 权限说明                                                     | 必要性       |
| :---------------------------------------------------- | ------------------------------------------------------------ | :----------- |
| ohos.permission.SYSTEM_FLOAT_WINDOW                   | 允许应用使用全局悬浮窗的能力。                               | 按需申请     |
| ohos.permission.INTERNET                              | 允许使用Internet网络。                                       | **基础权限** |
| ohos.permission.GET_NETWORK_INFO                      | 允许应用获取数据网络信息。                                   | **基础权限** |
| ohos.permission.ACCESS_CERT_MANAGER                   | 允许应用进行查询证书及私有凭据等操作。                       | 按需申请     |
| ohos.permission.RUNNING_LOCK                          | 允许应用获取运行锁，保证应用在后台的持续运行                 | **基础权限** |
| ohos.permission.PRINT                                 | 允许应用获取打印框架的能力。                                 | 按需申请     |
| ohos.permission.PREPARE_APP_TERMINATE                 | 允许应用关闭前执行自定义的预关闭动作。                       | **基础权限** |
| ohos.permission.ACCESS_BIOMETRIC                      | 允许应用使用生物特征识别能力进行身份认证。                   | 按需申请     |
| ohos.permission.FILE_ACCESS_PERSIST                   | 允许应用支持持久化访问文件Uri。                              | **基础权限** |
| ohos.permission.PRIVACY_WINDOW                        | 允许应用将窗口设置为隐私窗口，禁止截屏录屏。                 | 按需申请     |
| ohos.permission.WINDOW_TOPMOST                        | 允许窗口置顶。                                               | 按需申请     |
| ohos.permission.READ_PASTEBOARD                       | 允许应用读取剪贴板。                                         | **基础权限** |
| ohos.permission.READ_WRITE_DOWNLOAD_DIRECTORY         | 允许应用访问公共目录下Download目录及子目录，建议与ohos.permission.FILE_ACCESS_PERSIST同时申请。 | 按需申请     |
| ohos.permission.READ_WRITE_DOCUMENTS_DIRECTORY        | 允许应用访问公共目录下Documents目录及子目录，建议与ohos.permission.FILE_ACCESS_PERSIST同时申请。 | 按需申请     |
| ohos.permission.READ_WRITE_DESKTOP_DIRECTORY          | 允许应用访问公共目录下Desktop目录及子目录，建议与ohos.permission.FILE_ACCESS_PERSIST同时申请。 | 按需申请     |
| ohos.permission.LOCATION                              | 允许应用获取设备位置信息。                                   | 按需申请     |
| ohos.permission.APPROXIMATELY_LOCATION                | 允许应用获取设备模糊位置信息。                               | 按需申请     |
| ohos.permission.LOCATION_IN_BACKGROUND                | 允许应用在后台运行时获取设备位置信息。                       | 按需申请     |
| ohos.permission.MICROPHONE                            | 允许应用使用麦克风。                                         | 按需申请     |
| ohos.permission.CAMERA                                | 允许应用使用相机。                                           | 按需申请     |
| ohos.permission.ACCESS_BLUETOOTH                      | 允许应用接入蓝牙并使用蓝牙能力，例如配对、连接外围设备等。   | 按需申请     |
| ohos.permission.CUSTOM_SCREEN_CAPTURE                 | 允许应用截取屏幕内容。                                       | 按需申请     |

electron中需要ACL签名的权限包括（如果未申请到证书导致签名未通过，可以暂时将这几个权限注释掉）：

```
"requestPermissions": [
      {
        "name": "ohos.permission.SYSTEM_FLOAT_WINDOW"
      },
      ...
      {
        "name": "ohos.permission.READ_PASTEBOARD",
        "reason": "$string:access_pasteboard",
      },
      ...
      {
        "name": "ohos.permission.READ_WRITE_DOWNLOAD_DIRECTORY",
        "reason": "$string:reason_download",
        "usedScene": {
          "abilities": [
            "FormAbility"
          ],
          "when":"always"
        }
      },
      {
        "name": "ohos.permission.READ_WRITE_DOCUMENTS_DIRECTORY",
        "reason": "$string:reason_documents",
        "usedScene": {
          "abilities": [
            "FormAbility"
          ],
          "when":"always"
        }
      },
      {
        "name": "ohos.permission.READ_WRITE_DESKTOP_DIRECTORY",
        "reason": "$string:reason_desktop",
        "usedScene": {
          "abilities": [
            "FormAbility"
          ],
          "when":"always"
        }
      }
    ]
```

### 运行已签名的hap包

申请证书后在DevEco Studio中配置

![18](./res/16.png)

配置完成后点击右上角的run按钮即可运行

![19](./res/17.png)

或者

在命令行中执行命令安装hap包

```sh
hdc app install <已签名hap包路径>
# e.g: hdc app install pc_entry-default-signed.hap
```

![20](./res/12.png)

### 鸿蒙内的路径

[应用沙箱目录](https://docs.openharmony.cn/pages/v4.1/zh-cn/application-dev/file-management/app-sandbox-directory.md)

##### 应用沙箱路径和真实物理路径的对应关系

在应用沙箱路径下读写文件，经过映射转换，实际读写的是真实物理路径中的应用文件，应用沙箱路径与真实物理路径对应关系如下表所示。

其中<USERID>当前固定为100。

| 应用沙箱路径               | 物理路径                                          | 说明                      |
| :------------------------- | :------------------------------------------------ | :------------------------ |
| /data/storage/el1/bundle   | /data/app/el1/bundle/public/\<PACKAGENAME\>       | 应用安装包目录            |
| /data/storage/el1/base     | /data/app/el1/\<USERID\>/base/\<PACKAGENAME\>     | 应用el1级别加密数据目录   |
| /data/storage/el2/base     | /data/app/el2/\<USERID\>/base/\<PACKAGENAME\>     | 应用el2级别加密数据目录   |
| /data/storage/el1/database | /data/app/el1/\<USERID\>/database/\<PACKAGENAME\> | 应用el1级别加密数据库目录 |
| /data/storage/el2/database | /data/app/el2/\<USERID\>/database/\<PACKAGENAME\> | 应用el2级别加密数据库目   |

**用户数据需要存储在/data/storage/el2/base路径下，electron默认的--user-data-dir为/data/storage/el2/base/files**

![21](./res/app.getPath.png)

查看用户数据需要通过系统文件管理器，如下图：

![22](./res/fileManager.png)

![23](./res/fileManager-2.png)

### 定制自己的鸿蒙版应用

#### 替换应用名

位置：**ohos_hap\electron\src\main\resources\zh_CN\element\string.json**

替换文件中的**EntryAbility_label**字段的值即可。

![24](./res/13.png)

#### 替换图标

位置：**ohos_hap\AppScope\resources\base\media**

![25](./res/14.png)

#### 资源替换

由于鸿蒙暂时没有编译环境，如果原有项目需要编译，例如实际上ts需要编译转换为js再进行加载，则需要将编译产物js文件放到项目**web_engine/src/main/resources/resfile/resources/app**中。

开源三方库可能遇到的问题：

1. 如果 npm库里面使用了addon（也就是用C++来写库给js调用），未适配鸿蒙平台无法正常使用。-- 参考sqlite3编译的适配方案进行适配。注意：编译.node时C++版本最低要求为17。

2. 如果 npm库里面使用了process.platform、os.type()等查平台的API来判断平台，未适配鸿蒙平台无法正常使用。因为process.platform返回的是openharmony，三方库不一定认识它。 -- 需要修改代码，适配OH平台

3. 如果npm库里面有二进制文件（例如esbuild这样的库），无法正常使用。-- linux机器需要root权限，新PC走hnp方案，详见 [Electron HNP打包与fork指导文档](./docs/hnp-packaging-guide/README.md)

#### 多实例配置

如果应用不需要使用多实例，请将如下图所示的"multiAppMode"配置去掉
![](./images/multiAppMode.png)

## Electron鸿蒙特性说明

### 窗口

#### 首窗口指定大小

如果应用需要指定首窗口启动时的窗口尺寸，需要修改工程内文件**electron/src/main/module.json5**，向`abilities`内增加`metadata`属性，如下，如果不需要居中则只需要指定`width`和`height`。

```
{
  "module": {
    "name": "pc_entry",
    "type": "entry",
    "srcEntry": "./ets/Application/AbilityStage.ets",
    "description": "$string:module_desc",
    "mainElement": "EntryAbility",
    "deviceTypes": [
      "2in1"
    ],
    "deliveryWithInstall": true,
    "installationFree": false,
    "pages": "$profile:main_pages",
    "abilities": [
      {
        "name": "EntryAbility",
        "srcEntry": "./ets/entryability/EntryAbility.ets",
        "description": "$string:EntryAbility_desc",
        "icon": "$media:app_icon",
        "label": "$string:EntryAbility_label",
        "startWindowIcon": "$media:app_icon",
        "startWindowBackground": "$color:start_window_background",
        "launchType": "specified",
        "removeMissionAfterTerminate": true,
        "exported": true,
        ***************** 添加到这里 *****************
        "metadata": [
            {
                "name": "ohos.ability.window.height",
                "value": "800"
            },
            {
                "name": "ohos.ability.window.width",
                "value": "800",
            },
            {
                "name": "ohos.ability.window.left",
                "value": "center"
            },
            {
                "name": "ohos.ability.window.top",
                "value": "center",
            }
        ],
        *********************************************
        "skills": [
          {
            "entities": [
              "entity.system.home",
              "entity.system.browsable"
            ],
            "actions": [
              "action.system.home",
              "ohos.want.action.viewData"
            ],
            "uris": []
          }
        ]
      }
    ]
  }
}
```

#### 窗口显示隐藏

出于OH系统限制原因，窗口的显示隐藏与应用托盘强绑定，因此在启动应用前，为了保证窗口创建正常，需要先创建托盘。

```javascript
const { app, Tray } = require('electron');
const path = require('path');
app.whenReady().then(() => {
    let tray = new Tray(path.join(__dirname, 'tray_icon.png'));
    ...
})
```

如果应用不需要托盘和隐藏窗口，则需要修改**ohos_hap/web_engine/src/main/ets/adapter/AppWindowAdapter.ets**，注释掉`processMode`和`startupVisibility`属性。

```ts
...
    const options: StartOptions = {
      // processMode: contextConstant.ProcessMode.ATTACH_TO_STATUS_BAR_ITEM,
      // startupVisibility: param.show ? contextConstant.StartupVisibility.STARTUP_SHOW : contextConstant.StartupVisibility.STARTUP_HIDE,
      windowLeft: param.left - leftBorder,
      windowTop: param.top - topBorder,
      windowWidth: param.width + leftBorder + leftBorder,
      windowHeight: param.height + leftBorder + topBorder
    }
...
```

#### 调整三键

当前窗口三键效果与其他平台保持一致，创建除首窗口外的窗口时，如果窗口为有边框窗口（frame属性为true），则窗口三键为显示状态，若窗口为无边框窗口，那么窗口不显示三键，子窗口与悬浮窗无三键。

如果应用希望在创建无边框窗口时显示三键，可以通过修改WebAbility.ets中的初始状态调整创建窗口时三键的初始显示状态。如下图：

![30](./res/30.png)

###  新增接口

#### 悬浮窗

在`BrowserWindow`内新增 `windowInfo` 属性，是一个`Object`对象，该对象里目前只有一个属性 `type`，`type` 类型为`String`，取值是 `mainWindow`、`subWindow`、`floatWindow` 中的一个，默认取值是 `mainWindow`。

```js
let w = new BrowserWindow({
    windowInfo: {
       // type 的取值是 mainWindow subWindow floatWindow
       type: 'floatWindow'
    },
    parent: mainWindow;
    x:100,
    y:100,
    width:800,
    height: 600,
    show: true,
    // 可以设置背景色和透明度
    // 透明度的生效优先级顺序是 transparent、opacity 和 backgroundColor 里的alpha取值
    transparent: true, // 全透明
    opacity: 0.5, // 半透明
    backgroundColor: '#660000ee' // 半透明蓝色
});
w.loadURL("https://www.baidu.com");
```

#### systemPreferences 模块

##### 实现原生接口

##### `systemPreferences.getMediaAccessStatus(mediaType)`

- `mediaType` string - 可以是 `microphone`，`camera` 或 `screen`。

返回 `string` - 值可以是 `not-determined`， `granted`， `denied`， `restricted` 或 `unknown`。

获取麦克风、摄像头或截屏权限的状态，当前ohos平台仅返回`granted`与`denied`两种状态。

##### `systemPreferences.askForMediaAccess(mediaType)`

- `mediaType` string - 请求的媒体类型，可以是`microphone` 和 `camera`。

返回 `Promise<boolean>` - 如果用户允许授权或已授权则resolve `true`。系统授权弹窗仅会弹出一次，如果已经请求权限或请求被拒绝，*必须* 在 `设置` -> `隐私和安全` 中手动更改，不会弹出提醒，并且 promise 会返回现有的权限状态。

##### 新增请求权限接口

##### `systemPreferences.requestSystemPermission(permission)` 

- `permission` string - 下列值之一：

  `location`，`camera`，`microphone`，`screen-capture`，`user-download-dir`，`user-desktop-dir`，`user-document-dir`，`bluetooth`，`pasteboard`

返回 `Promise<boolean>` - 如果用户允许授权或已授权则resolve `true`。系统授权弹窗仅会弹出一次，如果已经请求权限或请求被拒绝，*必须* 在 `设置` -> `隐私和安全` 中手动更改，不会弹出提醒，并且 promise 会返回现有的权限状态。

##### `systemPreferences.requestDirectoryPermission(path)` 

- `path` string | null

返回 `Promise<boolean>` - 如果用户允许授权或已授权则resolve `true`，当 `path` 为 `null` 时，会同时请求用户下载、桌面、文档三个目录的权限，三个目录其中一个授权则resolve `true`。系统授权弹窗仅会弹出一次，如果已经请求权限或请求被拒绝，*必须* 在 `设置` -> `隐私和安全` 中手动更改，不会弹出提醒。

##### 新增打开系统设置中应用程序信息页接口

##### `systemPreferences.openApplicationInfoEntry()` 

打开 “系统设置”并进入应用程序信息页面。

#### `systemPreferences.fileAccessPersist(paths)`

- `paths` string[] - 需要持久化授权的文件或目录路径。

对传入的多个文件或目录持久化授权。

### Electron调用ETS指南

完整的 Electron 调用 ETS 指南，请参阅 [Electron调用ETS指导文档](./docs/electron-calling-ets-guide/README.md)。

该文档介绍如何在 Electron 鸿蒙版本中通过 aki 框架实现 C++ 与 ETS 的交互，包括：
- aki 源码下载和编译
- adapter 编写
- addon 编写
- ets 调用及 har 包构建


### Electron加载Addon指南

完整的 Electron 加载Addon 指南，请参阅 [Electron加载Addon指导文档](./docs/electron-loading-addon-guide/README.md)。

该文档以 node-sqlite3 为例，介绍如何在鸿蒙平台上为 Electron 加载原生 addon，包括：
- node-sqlite3 源码修改
- 编译环境配置
- addon 编译与集成


### callArkTSFunction 接口指南

完整的 callArkTSFunction 接口文档，请参阅 [callArkTSFunction接口文档](./docs/call-arkts-function-guide/README.md)。

该文档介绍 Electron JS 与 ArkTS 的交互通信机制，包括：
- 接口定义与参数说明
- 类型值映射表
- 使用示例与注意事项

### Deeplink使用指南

完整的 Deeplink 使用文档，请参阅 [Deeplink使用文档](./docs/deeplink/Deeplink使用文档.md)。

该文档介绍如何在 Electron 鸿蒙版本中实现 DeepLink（自定义协议），包括：
- 平台差异解析（Windows、macOS、Linux）
- OpenHarmony 适配方案
- module.json5 配置说明

### Electron HNP打包与fork指南

完整的 Electron HNP打包指南，请参阅 [Electron HNP打包指导文档](./docs/hnp-packaging-guide/README.md)。

该文档介绍在鸿蒙平台上通过 HNP 方案规避系统限制实现可执行二进制调用，并使用fork方法进行举例，具体内容包括：
- HNP 包构建与签名
- 集成到 Electron 工程
- fork 子进程 Demo
- 可执行二进制调用示例

### 子进程

子进程相关文档，请参阅 [子进程文档入口](./docs/child-process/README.md)。
**注意：需要提前打好electron二进制的HNP包，请参考上一小节**

- [exec](./docs/child-process/exec/exec.md) - 执行系统命令
- [execfile](./docs/child-process/execfile/execfile.md) - 执行可执行文件
- [fork](./docs/child-process/fork/fork.md) - 创建 Node.js 子进程
- [spawn](./docs/child-process/spawn/spawn.md) - 创建子进程



### 调试应用

#### 渲染进程

最广泛使用来调试指定渲染进程的工具是Chromium的开发者工具集。 它可以获取到所有的渲染进程，包括`BrowserWindow`的实例，`BrowserView`以及`WebView`。 您可以通过编程的方式在BrowserWindow的`webContents`中调用`openDevTool()`API来打开它们：

```javascript
const { BrowserWindow } = require('electron')

const win = new BrowserWindow()
win.webContents.openDevTools()
```

#### 主进程

使用如下的命令行开关来调试 Electron 的主进程:

**`--inspect=[port]`**

Electron 将监听指定 `port` 上的 V8 调试协议消息， 外部调试器需要连接到此端口上。 `port` 默认为 `9229`，可以修改为其他端口，指导文档内以`9229`端口为例。

以下是在`Windows`的`Chrome浏览器`中调试`OHOS`内`Electron`应用主进程的步骤，端口为`9229`：

1. 开启Electron命令行开关，在**ohos_hap/web_engine/src/main/ets/components/WebWindow.ets**文件中添加参数`inspect`并赋值为`'--inspect=9229' `，将变量添加到`vec_args`中，并重新打包安装。

```ts
// ohos_hap/web_engine/src/main/ets/components/WebWindow.ets
...
this.xComponent.attribute
      .backgroundColor(Color.Transparent)
      .onLoad(() => {
        let resDir = '--bundle-installation-dir=' + getContext().resourceDir;
        // 这里新建一个变量
        let inspect = '--inspect=9229';
        // 并添加到vec_args中
        let vec_args = ['--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36', resDir, inspect];
        this.electronRelaunchArgs.forEach((arg: string) => {
          vec_args.push(arg);
        })
        let nativeContext = JsBindingUtils.getNativeContext(ContextType.kMainProcess);
        nativeContext.runBrowser(vec_args);
      })
...
```

2. 配置端口转发，在命令行中，执行端口转发命令，执行结果如图。

```shell
hdc fport tcp:9229 tcp:9229
```

![26](./res/fport.png)

3. 访问下列网页来连接 Chrome  ，结果如图。

```shell
chrome://inspect
```

4. 进入`inspect`页面，点击页面内的`Configure...`按钮。

![27](./res/inspect.png)

5. 点击`Configure...`按钮，弹出菜单中存在 localhost:9229 即可，没有则需要配置。

![28](./res/inspect2.png)

6. 配置完成后，在工程机上开启electron应用，Windows的Chrome浏览器内会显示可调试的页面选项（可能需要一点时间），点击inspect即可远程调试electron主进程。

![29](./res/inspect-remote.png)

在使用命令行参数时，特别是那些涉及安全性的参数，需要谨慎操作以确保系统的安全性和稳定性，风险参数包括不限于命令行如下：

- `--remote-debugging-port`
  - 用途：启用远程调试功能，指定调试端口号。
  - 注意事项：确保调试端口仅在受信任的网络环境中开放，避免暴露在公共网络中，以防被恶意攻击。

- `--disable-web-security`
  - 用途：禁用同源策略，允许跨域请求。
  - 注意事项：仅在开发或测试环境中使用，切勿在生产环境中启用，以防止潜在的安全漏洞。

- `--no-sandbox`
  - 用途：禁用沙箱机制，降低进程隔离保护。
  - 注意事项：使用时需确保环境安全，避免恶意软件利用此配置进行攻击。

- `--ignore-certificate-errors`
  - 用途：忽略证书错误，允许自签名证书。
  - 注意事项：仅在受信任的环境中使用，避免在生产环境中启用，以防中间人攻击。

- `--gpu-launcher`
  - 用途：指定GPU进程的启动器命令。
  - 注意事项：主要用于高级调试或特定GPU配置，需了解其具体用法和潜在影响。

- `--inspect` 和 `--inspect-brk`
  - 用途：启动调试服务器，支持后台调试和启动时暂停。
  - 注意事项：避免在生产环境中使用，确保调试过程的安全性。

- `--host-rules`
  - 用途：配置网络请求的路由或重定向。
  - 注意事项：正确配置语法，确保网络请求的安全性和合规性。

总结：相关参数在开发和调试中非常有用，但需谨慎使用，确保环境安全，避免在生产环境中启用可能削弱安全性的参数。

### 命令行参数

完整的命令行参数支持说明，请参阅 [命令行参数支持说明](./docs/command-line-parameters/README.md)。

### 项目升级

完整的项目升级说明，请参阅 [electron鸿蒙项目升级文档](./docs/upgrade/README.md)。

### 上架问题

Electron应用在上架PC应用市场时若报错如下，请检测应用权限声明中是否包含仅2in1设备使用的权限。

若包含，提供两种解决思路：

1. 针对不需要上pad的应用：删除pad_entry模块。
2. 针对同时需要上pad和pc的应用：将仅2in1使用的权限声明由web_engine模块转移至pc_entry模块。

## 日志说明

Electron 框架日志说明，请参阅 [日志说明文档](./docs/logging-guide/README.md)。

- 包名信息与进程查看
- 根据包名查找进程
- Electron 框架日志模块（Adapter、WebEngine、Chromium）


## 问题定位

**崩溃问题需要提供对应日构建版本（例如：20241229.1）或代码提交的commit-id（可以使用`git log`命令查看，例如：162a67b2a0a2a6f36e47d4e6c10cb780dd8c99b4）及崩溃堆栈信息（在DevEco Studio内点击下图中的保存按钮可以将信息保存到本地）。**

![31](./res/31.png)

[点击可查看历史问题集](https://developer.huawei.com/consumer/cn/forum/topic/0204203363319759021?fid=0109140870620153026)

## 坚盾守护模式

坚盾守护模式是为高安全需求用户设计的系统级安全防护方案。该模式通过实施严格的功能限制，显著增强系统安全性，有效防范针对远程攻击面的各类威胁。在坚盾安全模式下，Electron增加了功能限制，需要开发者评估应用在坚盾模式下的可用性。

### 启用坚盾守护模式

要启用坚盾守护模式，请按以下路径操作：
1. 进入系统设置
2. 选择"隐私和安全"选项
3. 点击"坚盾守护模式"并开启

### 坚盾守护模式下的功能限制

为降低Electron受攻击风险，坚盾守护模式将实施以下关键安全限制：
- 全面禁用即时编译(JIT)功能，包括已获取 ACL 权限的应用程序
- 暂停 WebAssembly 支持（当前版本中 WebAssembly 依赖 JIT 功能实现）

### 应用兼容性评估指南

在坚盾守护模式下运行应用程序时，建议进行以下兼容性检查：
1. JavaScript 性能评估：
    - 测试应用在限制环境中的运行效率
    - 优化可能存在的性能瓶颈

2. WebAssembly 兼容性检查：
    - 静态代码分析：检查项目中的 WebAssembly 相关API调用，与第三方库的 Wasm 依赖情况。
    - 运行时验证：在坚盾守护模式下执行全功能测试。

参考文档：
- [查询设备安全模式](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/devicesecurity-securitymode)
- [JSVM坚盾守护模式](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/jsvm-secure-shield-mode)
- [ArkWeb坚盾守护模式](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/web-secure-shield-mode)
