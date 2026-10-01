#!/bin/bash
# Start (or check) the virtual screen used for headed captures: Xvfb :99 at 1680x1000x24 plus fluxbox.
# Usage: screen.sh start | stop | status
set -u
D=:99
DIR="$(cd "$(dirname "$0")" && pwd)"
case "${1:-start}" in
  start)
    if ! pgrep -f "Xvfb $D " >/dev/null; then
      nohup Xvfb $D -screen 0 1680x1000x24 -nolisten tcp >"$DIR/xvfb.log" 2>&1 &
      sleep 1
    fi
    if ! pgrep -f "fluxbox -rc $DIR/fluxbox-init" >/dev/null; then
      # own rc and apps files: no toolbar, no window decorations, every window maximized,
      # so the browser window owns the whole 1680x1000 screen
      printf '[app] (name=.*)\n  [Deco]\t{NONE}\n  [Maximized]\t{yes}\n[end]\n' >"$DIR/fluxbox-apps"
      printf 'session.configVersion:\t13\nsession.appsFile:\t%s\nsession.screen0.toolbar.visible:\tfalse\nsession.screen0.workspaces:\t1\n' "$DIR/fluxbox-apps" >"$DIR/fluxbox-init"
      DISPLAY=$D nohup fluxbox -rc "$DIR/fluxbox-init" >"$DIR/fluxbox.log" 2>&1 &
      sleep 1
    fi
    ;&
  status)
    pgrep -af "Xvfb $D " || echo "Xvfb not running"
    pgrep -af "fluxbox -rc" || echo "fluxbox not running"
    ;;
  stop)
    pkill -f "fluxbox -rc $DIR/fluxbox-init"; pkill -f "Xvfb $D "
    ;;
esac
