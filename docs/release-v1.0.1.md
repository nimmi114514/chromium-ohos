# Chromium for HarmonyOS v1.0.1

基于 Chromium 158.0.8116.0。本次主要新增部分 USB WebHID 适配。

## 更新内容

- 新增 USB HID 设备枚举、授权与连接支持。
- 接入 HID 报告描述符解析、输入/输出报告及 Feature 报告通道。
- 改进复合 USB 设备的接口处理和插拔事件处理。
- 已在实机通过 VIA 读取键盘布局；DualSense 在部分 USB 连接组合下可被识别、连接并读取输入。

## 已知限制

- WebHID 仍为部分适配，不代表兼容所有 HID 设备。
- 暂不支持通过蓝牙连接的 WebHID 设备。
- DualSense 震动尚未验证成功，其他高级反馈功能也不作支持承诺。
- 部分线材、连接组合及重复插拔场景仍可能出现设备识别问题。

应用版本为 **1.0.1**，内核版本为 **158.0.8116.0**。

感谢原版 [chromium-2in1-hap](https://github.com/Nyaacho0v0/chromium-2in1-hap) 作者及 OpenHarmony Chromium 移植社区提供的基础工作。
