#!/bin/sh
set -eu
TASK_BASE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$TASK_BASE/vendor" "$TASK_BASE/state/swift-cache"
/usr/bin/swiftc -O -target arm64-apple-macos14.0 -module-cache-path "$TASK_BASE/state/swift-cache" "$TASK_BASE/native/FileActions.swift" -o "$TASK_BASE/vendor/file-actions"
/usr/bin/codesign --force --sign - "$TASK_BASE/vendor/file-actions"
