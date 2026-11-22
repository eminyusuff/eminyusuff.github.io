#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.eminyusuff.academic-site-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs"
PHOTO_DIR="$HOME/Pictures/AcademicSiteInbox"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR" "$PHOTO_DIR" "$REPO_DIR/assets/events"
chmod +x "$REPO_DIR/macos/run_and_push.sh" "$REPO_DIR/macos/install.sh"

# Create dedicated Apple containers if they do not already exist.
osascript <<'APPLESCRIPT'
tell application "Calendar"
  if not (exists calendar "Academic Website") then
    make new calendar with properties {name:"Academic Website"}
  end if
end tell

tell application "Reminders"
  if not (exists list "Academic Website") then
    make new list with properties {name:"Academic Website"}
  end if
end tell
APPLESCRIPT

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>$REPO_DIR/macos/run_and_push.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>21600</integer>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/academic-site-sync.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/academic-site-sync-error.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

cat <<EOF
Installed $LABEL

Apple Calendar:  Academic Website
Apple Reminders: Academic Website
Photo inbox:     $PHOTO_DIR
Runs:            at login and every 6 hours while this Mac is available

macOS may ask for Calendar/Reminders Automation permissions on first run.
If Git push authentication is not configured on this Mac, authenticate GitHub once before relying on automatic pushes.
EOF
