# Elden Ring Death Counter for OBS

This tool watches `ER0000.sl2` while Elden Ring is running and publishes the
selected character's cumulative death count through a local web overlay for
OBS. It also writes a text file as a fallback.

The tool only reads the save. It never writes to or modifies `ER0000.sl2`.
Before parsing, it waits for the save to stop changing, takes a consistent
read, and validates the selected slot's MD5 checksum. Incomplete autosaves are
retried instead of being displayed.

## Requirements

- Windows
- Python 3.11 or newer (`py --version`)
- The PC version of Elden Ring

There are no third-party Python dependencies.

## Choose a character

From this folder, list the active characters:

```powershell
py -m death_counter --list
```

If the save has more than one character, choose its displayed slot number:

```powershell
py -m death_counter --slot 2
```

The save is automatically discovered beneath
`%APPDATA%\EldenRing\<SteamID>\ER0000.sl2`. If more than one Steam account is
present, specify the save:

```powershell
py -m death_counter `
  --save "$env:APPDATA\EldenRing\<SteamID>\ER0000.sl2" `
  --slot 2
```

You can also double-click `start_death_counter.bat`. It lists the active
characters and asks which slot to watch. After you enter a slot, leave the
window open; it remains running until you press `Ctrl+C`.

You can skip the prompt by launching it from a terminal with an argument:

```powershell
.\start_death_counter.bat --slot 2
```

## Add the browser overlay to OBS

1. Start the counter with the appropriate `--slot`.
2. In OBS, add a **Browser** source.
3. Set its URL to:

   ```text
   http://127.0.0.1:8765/overlay
   ```

4. Use a width of `600` and a height of `200`.
5. Leave the tracker running while OBS is using the source.

The overlay displays `Deaths: <number>` on one line. The label and number use
the same font, size, weight, and outline.

The server listens only on the local loopback interface. Other computers
cannot connect to it. To change the label:

```text
http://127.0.0.1:8765/overlay?label=attempts:
```

To display only the number:

```text
http://127.0.0.1:8765/overlay?label=
```

The text file remains available for an OBS **Text (GDI+)** source. Enable
**Read from file** and browse to `death_count.txt`.

The default file contains only the number, such as:

```text
1963
```

For a label in the file itself, use:

```powershell
py -m death_counter --slot 2 --format "Deaths: {deaths}"
```

Available format fields are:

- `{deaths}`
- `{name}`
- `{slot}`
- `{level}`
- `{hp}`
- `{max_hp}`
- `{base_max_hp}`

For example:

```powershell
py -m death_counter --slot 2 `
  --format "{name} | Deaths: {deaths} | HP: {hp}/{max_hp}"
```

## Behavior while the game is running

Elden Ring saves deaths to `ER0000.sl2`; the value is not read from game
memory. The output updates after the game completes an autosave, normally
about one second after the save file changes. It cannot display a death before
the game flushes that death to disk.

The stored value is cumulative for that character across New Game Plus cycles.
If a save is rolled back or replaced, the displayed value can decrease to
match the selected save.

Press `Ctrl+C` to stop the watcher.

## Build a standalone Windows executable

The release executable includes Python, so the target computer does not need
Python or pip installed. Building the executable does require Python:

```powershell
.\build_exe.ps1
```

The script creates an isolated `.venv-build`, installs the build dependency,
and produces:

```text
dist\EldenRingDeathCounter.exe
```

Double-click the executable, select a character slot, and leave its console
window open. `death_count.txt` is created beside the executable.

The executable is intentionally not packed with UPX.

## Options

```text
--save PATH             Explicit ER0000.sl2 path
--output PATH           OBS text path (default: death_count.txt)
--slot 1..10            Character slot
--character NAME        Character name instead of slot
--format TEMPLATE       Text written for OBS
--poll-interval SECONDS File check frequency (default: 0.25)
--settle-time SECONDS   Required quiet time before reading (default: 0.75)
--port PORT             Local OBS overlay port (default: 8765)
--no-overlay            Disable the OBS Browser Source server
--list                  List characters and exit
```

Run `py -m death_counter --help` for the complete command help.
