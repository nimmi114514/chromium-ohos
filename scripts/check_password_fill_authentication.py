#!/usr/bin/env python3
"""Execute production OHOS authentication/cache methods with a simulated OS.

This checks the native107 regression: enabling the setting must not authorize
an immediate fill through the shared profile authentication timestamp.
No device, account, or stored password data is used.
"""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def method(path, signature):
    text = (SRC / path).read_text()
    start = text.index(signature)
    body = text.index("{", start)
    end, depth = body + 1, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


common = "components/device_reauth/device_authenticator_common.cc"
ohos = "chrome/browser/device_reauth/ohos/device_authenticator_ohos.cc"
client = "chrome/browser/password_manager/chrome_password_manager_client.cc"
methods = "\n".join([
    method(common, "bool DeviceAuthenticatorCommon::NeedsToAuthenticate() const"),
    method(common, "void DeviceAuthenticatorCommon::RecordAuthenticationTimeIfSuccessful("),
    method(ohos, "void DeviceAuthenticatorOhos::AuthenticateWithMessage("),
    method(ohos, "void DeviceAuthenticatorOhos::OnAuthenticationCompleted("),
    method(client, "std::unique_ptr<device_reauth::DeviceAuthenticator>\nChromePasswordManagerClient::GetDeviceAuthenticator()"),
])

stub = r'''
#include <cassert>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#define BUILDFLAG(x) x
#define IS_OHOS 1
#define DCHECK(x) assert(x)
namespace base {
using TimeDelta = long;
inline long now = 100;
struct TimeTicks {
  long value;
  static TimeTicks Now() { return {now}; }
  friend long operator-(TimeTicks a, TimeTicks b) { return a.value-b.value; }
};
constexpr TimeDelta Seconds(long seconds) { return seconds; }
template<class... T> void UmaHistogramEnumeration(T&&...) {}
}
enum class ReauthResult { kSuccess, kFailure };
namespace device_reauth {
enum class DeviceAuthSource { kPasswordManager };
struct DeviceAuthParams {
  base::TimeDelta period;
  DeviceAuthParams(base::TimeDelta p, DeviceAuthSource) : period(p) {}
};
struct Callback {
  std::function<void(bool)> f;
  explicit operator bool() const { return bool(f); }
  void Run(bool result) { auto moved=std::move(f); f=nullptr; moved(result); }
};
struct DeviceAuthenticator {
  virtual ~DeviceAuthenticator() = default;
  virtual void AuthenticateWithMessage(const std::u16string&, Callback) = 0;
};
}
struct DeviceAuthenticatorProxy {
  std::optional<base::TimeTicks> timestamp;
  auto GetLastGoodAuthTimestamp() { return timestamp; }
  void UpdateLastGoodAuthTimestamp() { timestamp = base::TimeTicks::Now(); }
};
struct DeviceAuthenticatorCommon : device_reauth::DeviceAuthenticator {
  DeviceAuthenticatorProxy* device_authenticator_proxy_;
  base::TimeDelta auth_validity_period_;
  std::string auth_result_histogram_;
  DeviceAuthenticatorCommon(DeviceAuthenticatorProxy* p, base::TimeDelta period)
      : device_authenticator_proxy_(p), auth_validity_period_(period) {}
  bool NeedsToAuthenticate() const;
  void RecordAuthenticationTimeIfSuccessful(bool);
};
inline bool os_success = true, biometrics = true;
inline int os_calls = 0;
inline std::u16string last_prompt;
bool SimulatedOsAuthentication(const std::u16string& message) {
  ++os_calls; last_prompt=message; return os_success;
}
namespace password_manager_util_ohos {
bool AuthenticateUser(const std::u16string& message, bool) {
  return SimulatedOsAuthentication(message);
}
}
constexpr int IDS_PASSWORDS_AUTHENTICATION_PROMPT_PREFIX=1;
namespace l10n_util {
std::u16string GetStringFUTF16(int, const std::u16string& text) {
  return u"Chromium: " + text;
}
}
struct PlatformAuthenticator {
  bool AuthenticateUserWithNonBiometrics(const std::u16string& message) {
    return SimulatedOsAuthentication(message);
  }
};
struct DeviceAuthenticatorOhos : DeviceAuthenticatorCommon {
  using AuthenticateCallback=device_reauth::Callback;
  AuthenticateCallback callback_;
  std::unique_ptr<PlatformAuthenticator> authenticator_ =
      std::make_unique<PlatformAuthenticator>();
  using DeviceAuthenticatorCommon::DeviceAuthenticatorCommon;
  bool CanAuthenticateWithBiometrics() { return biometrics; }
  void AuthenticateWithMessage(const std::u16string&, AuthenticateCallback) override;
  void OnAuthenticationCompleted(bool);
};
struct Profile { DeviceAuthenticatorProxy proxy; };
struct FakeWebContents { int GetTopLevelNativeWindow() { return 1; } };
struct ChromeDeviceAuthenticatorFactory {
  static std::unique_ptr<device_reauth::DeviceAuthenticator> GetForProfile(
      Profile* p, int, const device_reauth::DeviceAuthParams& params) {
    return std::make_unique<DeviceAuthenticatorOhos>(&p->proxy, params.period);
  }
};
struct ChromePasswordManagerClient {
  Profile profile;
  FakeWebContents contents;
  Profile* GetProfile() { return &profile; }
  FakeWebContents* web_contents() { return &contents; }
  std::unique_ptr<device_reauth::DeviceAuthenticator> GetDeviceAuthenticator();
};
'''

cases = r'''
int main() {
  ChromePasswordManagerClient client;
  // Reproduce the old bypass: a successful setting change authorizes a fill
  // under the old 60-second shared-profile validity, without any OS call.
  client.profile.proxy.UpdateLastGoodAuthTimestamp();
  int callbacks=0, fills=0;
  auto fill = [&](bool success) { ++callbacks; if (success) ++fills; };
  DeviceAuthenticatorOhos old(&client.profile.proxy, base::Seconds(60));
  old.AuthenticateWithMessage(u"fill on example.test", {fill});
  assert(os_calls==0 && fills==1 && callbacks==1);
  fills=callbacks=0;
  // The actual production client must select zero validity on OHOS, so the
  // same timestamp (including exactly the same clock tick) cannot bypass OS.
  auto first = client.GetDeviceAuthenticator();
  first->AuthenticateWithMessage(u"fill on example.test", {fill});
  assert(os_calls==1 && fills==1 && callbacks==1);
  assert(last_prompt==u"fill on example.test");
  auto repeat = client.GetDeviceAuthenticator();
  repeat->AuthenticateWithMessage(u"fill on example.test", {fill});
  assert(os_calls==2 && fills==2 && callbacks==2);
  // OS cancellation/failure never runs a successful fill callback, even when
  // the shared profile has a recent successful authentication.
  os_success=false;
  auto failed = client.GetDeviceAuthenticator();
  failed->AuthenticateWithMessage(u"fill on example.test", {fill});
  assert(os_calls==3 && fills==2 && callbacks==3);
  // PIN-only devices follow the same per-fill gate.
  biometrics=false; os_success=true;
  auto pin = client.GetDeviceAuthenticator();
  pin->AuthenticateWithMessage(u"fill on example.test", {fill});
  assert(os_calls==4 && fills==3 && callbacks==4);
  assert(last_prompt==u"Chromium: fill on example.test");
  os_success=false;
  auto pin_failed = client.GetDeviceAuthenticator();
  pin_failed->AuthenticateWithMessage(u"fill on example.test", {fill});
  assert(os_calls==5 && fills==3 && callbacks==5);
  client.profile.proxy.timestamp.reset(); os_success=true;
  auto no_prior_auth = client.GetDeviceAuthenticator();
  no_prior_auth->AuthenticateWithMessage(u"fill on example.test", {fill});
  assert(os_calls==6 && fills==4 && callbacks==6);
}
'''

with tempfile.TemporaryDirectory(prefix="password-fill-auth-") as directory:
    cpp, binary = Path(directory) / "check.cc", Path(directory) / "check"
    cpp.write_text(stub + methods + cases)
    subprocess.run(["c++", "-std=c++20", "-Werror=return-type", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

report = {
    "passed": True,
    "productionClientAndAuthenticationMethodsExecuted": True,
    "osAuthenticationSimulated": True,
    "devicePasswordFillingVerified": False,
    "cases": ["old-60-second-setting-auth-reuse-reproduced",
              "immediate-fill-requests-authentication",
              "repeated-fill-requests-authentication",
              "failed-or-canceled-authentication-blocks-fill",
              "pin-only-fill-requests-authentication",
              "pin-failure-blocks-fill", "no-prior-authentication"],
}
(ROOT / "reports/native107-password-fill-authentication.json").write_text(
    json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
