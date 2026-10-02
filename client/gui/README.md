# Proxmark3 Studio — a GUI for the Iceman client

A clean, modern desktop front-end for the Proxmark3 (Iceman) client. It does
**not** replace the client or talk to the device directly — it launches the
same `proxmark3` binary you already build, keeps a live session, and gives you
buttons and forms instead of the terminal.

Because the UI is generated from `doc/commands.json`, **every** client command
gets its own form automatically (800+ commands, however many this checkout
ships), and it stays in sync with the client. Nothing is hand-coded per
command, so nothing is missed.

## What you get

- **Full command catalogue** — a searchable tree of every `hf` / `lf` / `data`
  / `hw` / `nfc` / `emv` / … command, each with a generated form for its flags
  and arguments, a live preview of the exact command line, and **Run** / **Copy**.
- **Descriptions everywhere** — every command and every command group shows a
  "What it does" line in the tree. Each form adds the full description, the
  group it belongs to, its usage line, and the client's own examples (click one
  to load it into the console). Search matches descriptions too, e.g. "magic".
- **Quick tasks** — one-click shortcuts for the common jobs (device version,
  antenna tuning, LF/HF auto-detect, MIFARE autopwn, read HID/EM410x/14a/iCLASS).
- **Live console** — the real client output, colour-coded by the client's own
  `[+]`/`[-]`/`[!]`/`[=]` tags, plus a command entry with history (↑/↓).
- **Stop button** — stops a long-running command (sniff, simulate, brute-force)
  the same way pressing Enter does in the CLI. If it won't stop, Disconnect
  force-kills the client.
- **Offline mode** — leave the port blank to start the client offline for
  demod, file, and analysis commands with no hardware attached.
- **Remembers** your client path, last port, and window size; pass `--port` to
  auto-connect on launch.
- **OLED-black theme** with a pastel ROYGBIV accent set; each command group has
  its own colour in the tree and quick tasks.

## Requirements

- A built `proxmark3` client from this repo (see `../../README.md` /
  `COMPILING.txt`).
- Python 3.8+ and PySide6.

```sh
pip install -r requirements.txt
```

## Run

From this directory:

```sh
./proxmark3-gui                       # auto-detects the client + commands.json
./proxmark3-gui --client ../proxmark3 --port /dev/ttyACM0
python3 -m pm3gui --help              # all options
```

- **Client** — path to the `proxmark3` binary (auto-detected from this
  checkout or `$PATH`; use **Browse**).
- **Port** — the serial device (e.g. `/dev/ttyACM0`, `/dev/tty.usbmodemXXX`,
  `COM4`). Leave blank to run offline. Likely ports are pre-filled.
- Press **Connect**. The status dot shows the device state reported by the
  client (`usb` / `fpc` / `offline`).

## Windows

1. Build the client with ProxSpace, following
   `doc/md/Installation_Instructions/Windows-Installation-Instructions.md`.
   You end up with `C:\ProxSpace\pm3\client\proxmark3.exe`. Build from this
   branch so the Stop button works (see Notes below).
2. Install Python 3 from https://www.python.org/downloads/ and tick
   **Add python.exe to PATH** during setup.
3. Double-click `client\gui\proxmark3-gui.cmd`. The first run installs
   PySide6. After that, `proxmark3-gui.pyw` starts the GUI without a console
   window.
4. Plug in the Proxmark3. It shows up in the Port list as `COMx — Proxmark3`
   and is selected automatically (use **Rescan** if you plug it in later).

The ProxSpace-built `proxmark3.exe` needs DLLs from ProxSpace's `msys2`
folder. The GUI adds them to the client's PATH automatically when the client
is inside a ProxSpace folder or ProxSpace is at `C:\ProxSpace`. If you see
"Could not start", point **Client** at the right `proxmark3.exe`.

## How it works

`pm3gui` runs the client in its normal interactive loop and pipes commands to
its stdin one at a time. The client echoes `[dev|script] pm3 --> <cmd>` before
each command, so pm3gui appends a short `rem` marker to every command line and
watches for that marker's echo to know when the command has finished — this is
how it splits and labels each command's output. No firmware or client changes
are required; it drives the stock binary.

| File | Role |
|------|------|
| `pm3gui/commands.py` | Parses `doc/commands.json` into the command/option model. |
| `pm3gui/session.py`  | Owns the client subprocess; queues commands, captures output. |
| `pm3gui/widgets/formbuilder.py` | Generates a form for one command. |
| `pm3gui/widgets/console.py` | Output pane + command entry with history. |
| `pm3gui/mainwindow.py` | Window: connection bar, command tree, forms, console. |
| `pm3gui/theme.py` | OLED-black + pastel ROYGBIV stylesheet and colour map. |
| `pm3gui/osutil.py` | Finds the client, its Windows DLL folders, and serial ports (Proxmark3 by USB ID). |
| `tools/smoke_test.py` | Headless end-to-end test against a real built client (also run in Windows CI). |
| `proxmark3-gui.cmd` / `.pyw` | Windows launchers. |
| `pm3gui/group_descriptions.json` | Group help ("hf 14a" → "ISO14443A RFIDs"), generated. |
| `tools/gen_group_descriptions.py` | Regenerates the above from the client's `command_t` tables. |

Command descriptions come from `doc/commands.json` (regenerated by `make
commands`). Group descriptions come from the client sources; after adding or
renaming a command group, run `python3 tools/gen_group_descriptions.py`.

## Notes / limits

- The GUI is a thin wrapper: it can only do what the client CLI can do. A few
  commands take positional or non-standard arguments the parser can't model as
  a field — every form has an **Extra arguments** box for those, and the
  console is always available.
- Interactive prompts *inside* a command (e.g. a confirmation) are answered by
  typing in the console.
- The **Stop** button sends Enter to the client. On Linux/macOS this is read
  from the pipe natively. On Windows the stock client reads key presses from a
  console that a background GUI process does not have — this repo includes a
  small `client/src/util.c` change so the Windows client also accepts the Enter
  from a pipe. Without that patch, use Disconnect (force-kill) to stop on
  Windows.
- Tested on Linux against a real built client (offline mode) with
  `tools/smoke_test.py`, including Stop. The same test runs in the Windows CI
  job (`.github/workflows/windows.yml`) against the ProxSpace-built client.
  Not yet tested with a physical Proxmark3 or on macOS.
