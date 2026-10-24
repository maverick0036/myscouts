#!/usr/bin/env bash
# Make Topic Scout start at login and restart if it crashes. Run once. Undo with: ./mac-autostart.sh off
set -euo pipefail
cd "$(dirname "$0")"
PLIST="$HOME/Library/LaunchAgents/com.topicscout.server.plist"
if [ "${1:-}" = "off" ]; then launchctl unload "$PLIST" 2>/dev/null || true; rm -f "$PLIST"; echo "Autostart removed."; exit 0; fi
mkdir -p "$HOME/Library/LaunchAgents" logs
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.topicscout.server</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$PWD/run.sh</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$PWD/logs/server.log</string>
  <key>StandardErrorPath</key><string>$PWD/logs/server.log</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Topic Scout will now start at login. Logs: $PWD/logs/server.log"
