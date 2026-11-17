# Windows gateway service setup

Follow [SKILL.md](../SKILL.md). Sasha decides whether to start or restart the gateway and performs approved recovery from an external shell. Do not record passwords or tokens.

## Autostart via HKCU Run or schtasks

`hermes gateway install` and direct `schtasks` calls from git-bash/MSYS may fail with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8f` (cp866 versus UTF-8) or `ERROR: Access is denied.` even for ONLOGON tasks without /RL HIGHEST.

HKCU\Run autostart does not require administrator privileges:

```python
import winreg

key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
vbs_path = r"C:\Users\<USER>\AppData\Local\hermes\gateway_hidden.vbs"
value = f'wscript.exe "{vbs_path}"'

key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
winreg.SetValueEx(key, "HermesGateway", 0, winreg.REG_SZ, value)
winreg.CloseKey(key)
```

Run using the Hermes venv Python:

```bash
/c/Users/<USER>/.local/share/hermes/hermes-agent/.venv/Scripts/python.exe script.py
```

To create a task without bash, a Python subprocess avoids the bash encoding issue:

```python
import subprocess
r = subprocess.run(["schtasks", "/Create", ...], capture_output=True)
print(r.stdout.decode("cp866", errors="replace"))
```

For an approved external manual start without reboot:

```bash
wscript.exe "C:\Users\<USER>\AppData\Local\hermes\gateway_hidden.vbs"
```

After 5–8 seconds check:

```bash
tail -5 ~/.local/share/hermes/logs/gateway.log
# Expected: [Telegram] Connected to Telegram (polling mode)
```

## Hidden startup without a visible CMD window

Task Scheduler may start the gateway with a visible CMD window. To hide it:

1. Create the VBS wrapper `~/.hermes/gateway_hidden.vbs` with synchronous execution and exit-code propagation. The original asynchronous command was:

```vbs
CreateObject("WScript.Shell").Run "C:\Users\<user>\AppData\Local\hermes\gateway-service\Hermes_Gateway.cmd", 0, False
```

This original example is asynchronous. For RestartOnFailure to receive the real gateway exit code, use the synchronous `bWaitOnReturn=True` plus `WScript.Quit(code)` behavior described in [gateway-crash-history.md](gateway-crash-history.md).

2. Recreate the task from XML (administrator privileges required):

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><UserId>USERNAME</UserId></LogonTrigger>
  </Triggers>
  <Settings>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>wscript.exe</Command>
      <Arguments>C:\Users\USERNAME\AppData\Local\hermes\gateway_hidden.vbs</Arguments>
    </Exec>
  </Actions>
</Task>
```

3. In an administrator CMD:

```cmd
schtasks /Delete /TN "Hermes_Gateway" /F
schtasks /Create /TN "Hermes_Gateway" /XML "C:\Users\USERNAME\AppData\Local\Temp\hermes_task.xml"
```

`Set-ScheduledTask` in PowerShell requires administrator privileges; use the `schtasks` CLI. After `hermes gateway restart`, Hermes may recreate the task and the window may reappear; repeat the setup if needed. Check the venv path in `gateway-service/Hermes_Gateway.cmd` after a Hermes update: it may contain the old `hermes-agent\venv\` instead of `hermes-agent\.venv\`. The correct path is `C:\Users\<USER>\AppData\Local\hermes\hermes-agent\.venv\Scripts\python.exe`.

## Delegation configuration

`delegation.model`, `delegation.provider` and `delegation.base_url` are read from `CLI_CONFIG` at process startup. Changes through `hermes config set` require a restart to take effect; otherwise subagents continue using the old model. The command for an approved external restart is:

```bash
hermes gateway restart
```

## Screen lock and sleep

Screen lock (Win+L) does not interrupt the gateway, network, VPN or background cron jobs. Sleep/hibernate stops the gateway, VPN and cron jobs; check sleep settings before overnight work.

```bash
powercfg.exe -query 2>&1 | grep -A3 "SUB_SLEEP"
# STANDBYIDLE: 0x00000000 means disabled; otherwise the value is seconds
# 0x00001c20 = 7200 seconds = 2 hours (typical Windows AC default)
```

Disable sleep overnight:

```bash
powercfg.exe -change standby-timeout-ac 0   # AC power
powercfg.exe -change standby-timeout-dc 0   # battery
```

Restore after work:

```bash
powercfg.exe -change standby-timeout-ac 120   # 2 hours on AC
powercfg.exe -change standby-timeout-dc 180   # 3 hours on battery
```

`powercfg /query SCHEME_CURRENT SUB_SLEEP` may produce empty output through bash because of encoding. Use `powercfg.exe -query 2>&1 | cat` to see the complete list including SUB_SLEEP.

## Historical context

The asynchronous VBS example above predates the synchronous wrapper fix needed for Task Scheduler to observe failure exit codes; see [gateway-crash-history.md](gateway-crash-history.md).
