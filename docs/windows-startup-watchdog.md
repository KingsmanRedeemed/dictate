# Windows Startup Watchdog

This machine uses a per-user watchdog to keep Dictate running after logon and to relaunch it if the
daemon exits.

## What was fixed

- Windows had no durable Dictate startup entry, so the controls app could be running while the
  headless daemon was not.
- A per-user startup shortcut and `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` entry were
  added for `scripts\dictate-watchdog.ps1`.
- The watchdog uses a named mutex so duplicate startup paths do not create duplicate watchdogs.
- The watchdog replaces any Dictate daemon that is running with the wrong startup profile.

## Startup profile

The current Windows profile is:

```text
dictate.exe --no-tray --type-backend pynput --stt-backend whisper-cpp --model large-v3-turbo-q5_0 --device auto --compute-type int8 --language en
```

This was chosen after a local benchmark on this machine:

```text
faster-whisper / turbo / auto:          9.6s latency for a 9.5s sample
whisper-cpp / large-v3-turbo-q5_0:     1.6s latency for the same sample
```

Both produced the same measured WER on that benchmark sample. `--language en` is pinned to avoid
language detection overhead during normal English dictation.

## Machine startup wiring

The current per-user startup entries are:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Dictate Watchdog.lnk
HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Dictate Watchdog
```

Both launch:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Users\eliro\Repos\Dictate\scripts\dictate-watchdog.ps1
```

## Fast checks

Confirm the watchdog and daemon are running:

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    ($_.Name -like 'powershell*' -and $_.CommandLine -like '*dictate-watchdog.ps1*') -or
    ($_.Name -eq 'dictate.exe' -and $_.CommandLine -like '*--no-tray*') -or
    ($_.Name -eq 'whisper-server.exe')
  } |
  Select-Object ProcessId,Name,CommandLine
```

Confirm the Dictate runtime is healthy:

```powershell
.\.venv\Scripts\python.exe -m dictate doctor --quick --type-backend pynput --stt-backend whisper-cpp --model large-v3-turbo-q5_0 --device auto
```

Check startup logs:

```powershell
Get-Content "$env:LOCALAPPDATA\dictate\logs\latest.log" -Tail 120
Get-Content "$env:LOCALAPPDATA\dictate\logs\watchdog.log" -Tail 40
```

## Lag diagnosis

The daemon now logs successful dictations with:

```text
[audio=Ns, processing=Ns, queued=N]
```

- `audio` is the recorded audio duration.
- `processing` is the actual transcription time.
- `queued` shows whether additional recordings were waiting behind the current transcription.

If `processing` is high relative to `audio`, benchmark or switch STT backend/model. If `queued` is
above zero, the user is recording faster than the backend is completing transcriptions.
