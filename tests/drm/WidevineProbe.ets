// Temporary native DRMKit capability probe. No certificates, licenses or
// challenges are requested or recorded. Remove before final delivery.
import drm from '@ohos.multimedia.drm';
import hilog from '@ohos.hilog';
import { BusinessError } from '@kit.BasicServicesKit';

class DrmProbeResult {
  name: string = '';
  supported: boolean = false;
  supportError: number = 0;
  avc: boolean = false;
  hevc: boolean = false;
  aac: boolean = false;
  mimeError: number = 0;
  created: boolean = false;
  createError: number = 0;
  maxProtectionLevel: number = 0;
  released: boolean = false;
}

function probeLog(value: string): void {
  hilog.error(0x0000, 'chromium', '[WidevineProbe] %{public}s', value);
}

export function runWidevineProbe(): void {
  probeLog('started');
  try {
    const names: string[] = drm.getMediaKeySystems().map((info: drm.MediaKeySystemDescription): string => info.name);
    probeLog('plugins=' + JSON.stringify(names));
  } catch (error) {
    probeLog('enumerationError=' + (error as BusinessError).code);
  }
  for (const name of ['com.widevine.alpha', 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
    'edef8ba979d64acea3c827dcd51d21ed', 'com.wiseplay.drm']) {
    const result: DrmProbeResult = new DrmProbeResult();
    result.name = name;
    try {
      result.supported = drm.isMediaKeySystemSupported(name);
    } catch (error) {
      result.supportError = (error as BusinessError).code;
    }
    try {
      result.avc = drm.isMediaKeySystemSupported(name, 'video/avc');
      result.hevc = drm.isMediaKeySystemSupported(name, 'video/hevc');
      result.aac = drm.isMediaKeySystemSupported(name, 'audio/mp4a-latm');
    } catch (error) {
      result.mimeError = (error as BusinessError).code;
    }
    try {
      const system: drm.MediaKeySystem = drm.createMediaKeySystem(name);
      result.created = true;
      try {
        result.maxProtectionLevel = system.getMaxContentProtectionLevel();
      } finally {
        system.destroy();
        result.released = true;
      }
    } catch (error) {
      result.createError = (error as BusinessError).code;
    }
    probeLog('result=' + JSON.stringify(result));
  }
}
