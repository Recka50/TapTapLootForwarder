# TapTapLoot Forwarder

Forward keyboard input to [TapTapLoot](https://store.steampowered.com/app/your_app_id) running in Xwayland on Linux, so it can run in the background while you use other apps — similar to how BongoCat works.

> **Based on [BongoCatXP](https://github.com/ITJesse/BongoCatXP) by ITJesse** — adapted for TapTapLoot with Xwayland support and dynamic xauth handling.

## How it works

TapTapLoot is launched in a rootful Xwayland instance (via a Steam launch script), which lets it run independently of your Wayland compositor. This tool uses `evdev` to read your keyboard at the device level and forwards keypresses to the TapTapLoot window via `xdotool`, without requiring the window to have focus.

## Requirements

- Linux (Wayland or X11)
- Python 3.7+
- `xdotool`
- Access to `/dev/input/` devices (via `input` group)
- TapTapLoot running via the Xwayland launch script (see below)

## Installation

### 1. Install system dependencies

```bash
# Arch Linux
sudo pacman -S xdotool python-pipx

# Fedora / Nobara
sudo dnf install xdotool pipx

# Debian / Ubuntu
sudo apt install xdotool pipx
```

> **Bazzite / immutable distros:** See the [Bazzite section](#bazzite--immutable-distro-installation) below.

### 2. Install this tool

```bash
# From this repo
pipx install git+https://gitea.recka.tech/bepis/TapTapLootForwarder.git

# Or from a local clone
git clone https://gitea.recka.tech/bepis/TapTapLootForwarder.git
cd TapTapLootForwarder
pipx install .
```

### 3. Add yourself to the input group

```bash
sudo usermod -aG input $USER
# Log out and back in for this to take effect
```

## Steam Launch Script

Save the following as `~/.local/bin/taptaploot-forward.sh` (or download from the repo above) and make it executable (`chmod +x`):

```bash
#!/bin/bash
# Launches TapTapLoot in rootful Xwayland
# Steam launch option: ~/.local/bin/taptaploot-forward.sh %command%

for i in $(seq 10 30); do
    if [ ! -e "/tmp/.X11-unix/X$i" ]; then
        GAME_DISPLAY=":$i"
        break
    fi
done

GAME_XAUTH=$(mktemp /tmp/taptaploot-xauth.XXXXXX)
COOKIE=$(mcookie)
xauth -f "$GAME_XAUTH" add "$GAME_DISPLAY" . "$COOKIE"

cleanup() {
    kill "$XWAYLAND_PID" 2>/dev/null
    wait "$XWAYLAND_PID" 2>/dev/null
    rm -f "$GAME_XAUTH"
}
trap cleanup EXIT INT TERM

XAUTHORITY="$GAME_XAUTH" Xwayland "$GAME_DISPLAY" -geometry 1920x1080 -noreset -auth "$GAME_XAUTH" &
XWAYLAND_PID=$!
sleep 1

DISPLAY="$GAME_DISPLAY" XAUTHORITY="$GAME_XAUTH" "$@" &
GAME_PID=$!

wait "$GAME_PID"
```

Set your Steam launch option to:
```
~/.local/bin/taptaploot-forward.sh %command%
```

## Usage

1. Launch TapTapLoot via Steam (using the launch script above)
2. In a terminal, run:

```bash
taptaploot-forwarder
```

Keypresses will be forwarded to the game without it needing focus. Press `Ctrl+C` to stop.

## Bazzite / Immutable Distro Installation

On Bazzite or SteamOS (which have immutable root filesystems), `pacman` and other package managers can't install packages directly to the host. The recommended approach is a **Distrobox container**:

```bash
# Create an Arch-based container (Bazzite has a shortcut for this)
ujust distrobox-arch
# or manually:
distrobox create --name taptaploot --image archlinux:latest
distrobox enter taptaploot

# Inside the container:
sudo pacman -S xdotool python-pipx
sudo usermod -aG input $USER
pipx install git+https://gitea.recka.tech/bepis/TapTapLootForwarder.git

# Export the command to your host so you can run it outside the container
distrobox-export --bin ~/.local/bin/taptaploot-forwarder
```

Then run `taptaploot-forwarder` from your host terminal as normal.

> **Note:** The `input` group change inside the container may still require a full logout/login on the host to take effect. If you get permission errors, try running `sudo taptaploot-forwarder` temporarily inside the container.

## Troubleshooting

**Permission denied on `/dev/input/`** — make sure you've added yourself to the `input` group and logged out/in. Temporarily use `sudo taptaploot-forwarder`.

**Window not found** — ensure TapTapLoot is running via the Xwayland launch script. The forwarder checks every 10 seconds.

**No keyboard devices found** — permission issue, see above.

## Credits

- [BongoCatXP](https://github.com/ITJesse/BongoCatXP) by [ITJesse](https://github.com/ITJesse) — original implementation this is based on
- MIT License
