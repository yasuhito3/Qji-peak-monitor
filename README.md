# Qji Peak Monitor

**English | [日本語](README.ja.md)**

A standalone real-time audio peak meter for Qji（奏在）'s final output stage.
It reads the log written by ffmpeg's `astats` filter and displays it as an
analog-VU-style stereo needle meter, a horizontal peak level bar, and a
signal history graph.

![screenshot placeholder](assets/icon_256.png)

## Features

- Stereo needle meter (L/R) + horizontal peak level meter
- SIGNAL PROFILE graph showing recent signal history
- PEAK HIT counter that detects threshold crossings
- **Display Delay** feature to correct the gap between the meter and what
  you actually hear (common with DSP playback, ALSA/loopback buffering, etc.)
  - Set an initial offset in seconds at launch with `--display-delay`
  - Fine-tune it live while the app is running:
    - `←` / `→` : adjust by 0.1s
    - `↑` / `↓` : adjust by 0.5s
    - Type a number directly (e.g. `9` → `.` → `5`) and press `Enter` to confirm
    - `r` : reset to the value given at launch
- Always-on-top window, with a customizable initial window size

## Requirements

- Linux (developed and tested on Xubuntu / Ubuntu, X11 environment assumed)
- Python 3
- `python3-tk`
- `matplotlib`
- `numpy`
- `ffmpeg` (Qji itself must be writing an `astats` log)

## Installation

### Option A: Double-click installer (no terminal required)

1. Download this repository as a ZIP (or `git clone` it) and extract it
2. Double-click **"Qji Peak Monitor をインストール" / "Install Qji Peak Monitor"**
   (`INSTALL.desktop`) inside the extracted folder
3. If a "Do you trust this application?" dialog appears (common on first run),
   choose "Trust and Launch"
4. A terminal window will open and run the installer. When it finishes, it
   will show `Press Enter to close this window…` — press Enter to close it

This registers "Qji Peak Monitor" in your application menu and adds a
desktop icon. From then on, just double-click that icon to launch the app.

> If double-clicking does nothing, or you're asked to "choose an application
> to open this file", try Option B (terminal installation) instead. Some file
> managers don't allow running `.desktop` files by default.

### Option B: Install from the terminal

```bash
git clone https://github.com/<your-username>/qji-peak-monitor.git
cd qji-peak-monitor
bash install.sh
```

> Running it as `bash install.sh` (rather than `./install.sh`) works even if
> the executable permission bit was lost — for example after downloading via
> GitHub's "Download ZIP", or after files were moved around through GitHub's
> web UI. No `chmod` or `sudo` needed.

Either way, `install.sh` will:

- Check for required dependencies (`python3-tk` / `matplotlib` / `numpy`)
- Copy the app into `~/.local/share/qji-peak-monitor/`
- Create a launcher at `~/.local/bin/qji-peak-monitor`
- Register the app in your application menu
  (`~/.local/share/applications/`)
- Add a desktop shortcut

Everything is installed under your home directory, so `sudo` is never
required (if a dependency is missing, the installer will simply print the
`apt install` command you need to run).

### Uninstall

```bash
bash uninstall.sh
```

> If double-clicking `INSTALL.desktop` doesn't do anything, it's usually the
> same permission-bit issue — try `bash install.sh` from a terminal instead.
> (If you'd rather restore the executable bit directly:
> `chmod +x install.sh uninstall.sh INSTALL.desktop`.)

## Usage

Launch it from the desktop icon or application menu, or from a terminal:

```bash
qji-peak-monitor [options]
```

### Main options

| Option | Description | Default |
|---|---|---|
| `--log-glob` | Glob pattern for the astats log file to watch | (built-in default) |
| `--threshold` | Peak-hit detection threshold (dBFS) | (built-in default) |
| `--window` | Time span shown on the SIGNAL PROFILE graph (seconds) | 20.0 |
| `--floor` | Meter floor (dBFS) | (built-in default) |
| `--width-scale` | Initial window width scale factor | 0.5 |
| `--height-scale` | Initial window height scale factor | 1.0 |
| `--no-topmost` | Disable always-on-top | (on by default) |
| `--display-delay` | Seconds to delay the display by, to match what you actually hear | 0.0 |
| `--refresh-ms` | Screen refresh interval (ms) | 100 |

Example (DSP playback, starting with a 2.5s delay):

```bash
qji-peak-monitor --display-delay 2.5
```

### Keyboard shortcuts (while running)

| Key | Action |
|---|---|
| `0`–`9`, `.` | Start direct numeric entry for the display delay |
| `Enter` | Confirm the entered value |
| `Backspace` | Delete the last character while typing |
| `Esc` | Cancel entry |
| `←` / `→` | Adjust display delay by 0.1s |
| `↑` / `↓` | Adjust display delay by 0.5s |
| `r` | Reset display delay to the value given at launch |

## How it works

The `astats` filter measures the signal at the very end of ffmpeg's filter
chain, right before the audio is handed off to the next stage. This means
the right edge of the SIGNAL PROFILE graph represents "the moment ffmpeg
finished processing and passed the audio onward" (to ALSA output or a DSP
loopback) — not the moment you actually hear it. Downstream buffering (ALSA
buffers, a DSP queue, etc.) adds further delay before the sound reaches your
speakers, which is what `--display-delay` compensates for.

## License

MIT — see [LICENSE](./LICENSE).
