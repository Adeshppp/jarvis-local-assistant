#!/bin/sh
set -eu
TASK_BASE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TASK_APP="$TASK_BASE/Jarvis.app"
mkdir -p "$TASK_APP/Contents/MacOS" "$TASK_APP/Contents/Resources" "$TASK_BASE/state/swift-cache"
"$TASK_BASE/scripts/build-file-actions.sh"
/usr/bin/swiftc -O -target arm64-apple-macos14.0 -module-cache-path "$TASK_BASE/state/swift-cache" -framework AppKit -framework WebKit -framework AVFoundation -framework Security "$TASK_BASE/native/Jarvis.swift" -o "$TASK_APP/Contents/MacOS/Jarvis"
printf '%s\n' "$TASK_BASE" > "$TASK_APP/Contents/Resources/project-root.txt"
cat > "$TASK_APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Jarvis</string><key>CFBundleIdentifier</key><string>local.personal-ai.desktop</string><key>CFBundleName</key><string>Jarvis</string><key>CFBundleVersion</key><string>2</string><key>CFBundleShortVersionString</key><string>0.2.0</string><key>LSUIElement</key><true/><key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSMicrophoneUsageDescription</key><string>Jarvis processes your voice on your own Mac using offline speech models.</string>
<key>NSLocalNetworkUsageDescription</key><string>Connect only to your personal assistant server on your private network.</string>
</dict></plist>
PLIST
/usr/bin/codesign --force --sign - --identifier local.personal-ai.desktop "$TASK_APP"
printf 'Built %s\n' "$TASK_APP"
