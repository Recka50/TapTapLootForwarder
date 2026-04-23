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

XAUTHORITY="$GAME_XAUTH" Xwayland "$GAME_DISPLAY" -geometry 400x300 -noreset -auth "$GAME_XAUTH" &
XWAYLAND_PID=$!
sleep 1

DISPLAY="$GAME_DISPLAY" XAUTHORITY="$GAME_XAUTH" "$@" &
GAME_PID=$!

wait "$GAME_PID"