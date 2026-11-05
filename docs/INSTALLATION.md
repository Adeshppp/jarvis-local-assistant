# Installing Jarvis

This is the source setup I used for my Apple Silicon Mac. It is still a hands-on installation, especially the external-drive step. The current storage initializer expects a mounted 4 TB USB SanDisk Extreme 55DD. Other hardware needs an intentional change to the initializer, not a bypass of its checks.

If the app is already installed and working, skip to **Updating my existing installation** below. Do not run fresh storage initialization again.

## What I need first

- Apple Silicon Mac. The app targets macOS 14+, with the current build tested on my M1/macOS 27.2 host.
- Python 3.12, Git, curl, and Apple’s command line developer tools (`xcode-select --install` if they are missing).
- Enough space on the external drive for two language models, speech models, cache, and backups.
- Internet for initial downloads. Normal local conversation can work offline afterwards.
- Permission to approve my own microphone, Keychain, local-network, and protected-file prompts in macOS.

I’m not including a virtual environment, prebuilt app, private configuration, or model binaries in Git. Build them on the target machine.

## 1. Put the checkout in Application Support

Use a new destination; don’t clone over an existing installation. This is a private repository, so GitHub authentication is required.

```sh
JARVIS_DIR="$HOME/Library/Application Support/PersonalAI-Local"
mkdir -p "$HOME/Library/Application Support"
git clone https://github.com/Adeshppp/jarvis-local-assistant.git "$JARVIS_DIR"
cd "$JARVIS_DIR"
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
./jarvis setup
```

`setup` creates the local database, first device token, configuration, and private TLS certificates. Keep `state/` private. The native app will transfer the initial device token into Keychain when first opened.

Application Support avoids the earlier problem where a background service could not read source stored in Documents. Don’t move a working virtual environment and assume all of its launchers will still work.

## 2. Allocate owned model storage once

Before downloading models, check whether suitable models are already available on the internal drive from previous local AI tools. Use known app/model locations; do not scan my unrelated external-drive data. The initial host audit found no models to reuse.

For a new installation on the expected drive, check disk metadata and then let the initializer create a new owned folder:

```sh
diskutil info /Volumes/Sandisk
PYTHONPATH=. .venv/bin/python - <<'PY'
from assistant.config import STATE
from assistant.storage import initialize
binding = initialize(STATE / 'storage.json', '/Volumes/Sandisk')
print('Created owned storage:', binding['root'])
PY
```

This allocates a new `Personal_AI_Assistant` folder, or a unique alternative if that name is already taken. It records the mounted volume’s identity and does not reuse or inspect an existing candidate folder. If initialization is interrupted or reports an existing binding, stop and inspect the private binding state; do not delete it and retry casually.

The existing working host already has its binding and folder. This step must be skipped there.

## 3. Install the local model runtime

The development build used the official Ollama 0.40.14 archive. Download it inside the ignored working directory and verify the release checksum before extraction:

```sh
mkdir -p work vendor/ollama
curl --fail --location --output work/ollama-darwin.tgz \
  https://github.com/ollama/ollama/releases/download/v0.40.14/ollama-darwin.tgz
.venv/bin/python - <<'PY'
import hashlib
from pathlib import Path
p = Path('work/ollama-darwin.tgz')
expected = 'f3bf9a528e908da0da5a2b3a4ad3252a369d62186501dc4880261e8d9023bff5'
if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
    raise SystemExit('Archive checksum mismatch; do not extract it')
print('Archive checksum matches the pinned release')
PY
tar -xzf work/ollama-darwin.tgz -C vendor/ollama
```

The checksum above matched the official release asset and the downloaded archive during setup. Review the runtime and model licences before redistribution or other uses.

In terminal A, from this checkout, start the sandboxed foreground model server:

```sh
PYTHONPATH=. .venv/bin/python scripts/serve-models.py
```

In terminal B, from the same checkout, download only the models needed for this setup:

```sh
OLLAMA_HOST=127.0.0.1:11435 vendor/ollama/ollama pull qwen3.5:2b
OLLAMA_HOST=127.0.0.1:11435 vendor/ollama/ollama pull qwen3.5:4b
```

The foreground server sets the model directory to the bound SSD folder and turns Ollama cloud mode off. Once downloads finish, stop terminal A with Control-C before starting the managed service. Don’t leave another server competing for port 11435.

## 4. Install speech and browser assets, then build the app

```sh
PYTHONPATH=. .venv/bin/python scripts/download_speech.py
PLAYWRIGHT_BROWSERS_PATH="$PWD/state/browser-binaries" \
  .venv/bin/python -m playwright install chromium
scripts/build-mac.sh
```

Speech assets go into owned SSD storage. The downloader rejects unsafe archive paths and refuses to overwrite extracted files. It is not yet a resumable installer: if interrupted, inspect what was created before attempting recovery.

The native build also compiles the file-action helper. It is locally ad hoc signed, not notarised for public distribution. Don’t disable system security checks if a new machine needs an ordinary app approval.

## 5. Choose runtime access and models

Fresh defaults start in restricted mode. The following explicit configuration matches the broad personal-file access I requested for my own assistant:

```sh
PYTHONPATH=. .venv/bin/python - <<'PY'
import sys
from pathlib import Path
from assistant.config import BASE, STATE, load, save
cfg = load()
cfg.update(model='qwen3.5:2b', tool_model='qwen3.5:4b',
           models=['qwen3.5:2b', 'qwen3.5:4b'], context=6144,
           max_tokens=320)
cfg['filesystem'] = {'mode': 'full', 'ssd_mount': '/Volumes/Sandisk',
                     'helper': str(BASE / 'vendor/file-actions')}
cfg['web'] = {'headless': False}
save(cfg)
app = Path(sys.base_prefix) / 'Resources/Python.app'
if app.exists():
    marker = STATE / 'backend-app.txt'
    marker.write_text(str(app))
    marker.chmod(0o600)
print('Configured. macOS permissions still need approval on this machine.')
PY
./jarvis install
open Jarvis.app
```

The backend runs as my user; model storage still has its own sandbox. File writes, edits, moves, Trash, and permanent-file deletion require the tool approval flow. Full mode does not grant root privileges or bypass macOS protections.

For protected folders, use **File access permissions…** in Jarvis and add/enable the indicated backend Python.app in **System Settings → Privacy & Security → Full Disk Access**. Use **Reveal Python app** to locate it. Restart the service after granting access. Add the backend interpreter identified by the running installation, not an unrelated Python executable.

Allow Jarvis’s microphone request when testing voice. Passwords and OS permission approvals belong in macOS dialogs, never in chat.

## 6. Check the installation

```sh
./jarvis status
./jarvis chat 'Say hello in one sentence.'
```

Open the menu bar window and try typing first. Then use **Wake listening**, say “Hey Jarvis,” wait for the acknowledgement, and ask a short question. Test file changes on a disposable file and inspect the approval preview. If the SSD is unavailable, reconnect the correct drive and wait for the runtime monitor.

See [the user guide](USER_GUIDE.md) for troubleshooting and [validation notes](TESTING.md) before running diagnostics.

## Optional private-network clients

```sh
./jarvis lan on
./jarvis restart
PYTHONPATH=. .venv/bin/python scripts/prepare-devices.py
./jarvis pair iphone
```

Pairing writes a private per-device credential under `device-connections/`. Transfer it directly to the device; don’t commit it or paste it into an issue. The browser client accepts a token in its connect form. Certificate enrolment files are generated separately; verify the server fingerprint through a trusted local channel.

On iPhone, install only my generated private CA profile, then explicitly enable trust for that CA in the device’s certificate trust settings. Use the generated local server address, not an example IP copied from a document. Physical iPhone setup and voice still need testing on my actual phone.

For an Apple Silicon Mac client, `scripts/build-remote-client.py` packages a lightweight client with public pins and no embedded device token. A remote-action companion uses `./jarvis pair mac-mini --target mac-mini`, a backend restart, and `python -m assistant.companion --help` for its local setup. It only offers limited actions currently. Check the target Mac’s architecture and OS first.

New pairings have limited scopes. Do not grant all tools to every device automatically. No public exposure, Tailscale connection, or router forwarding is part of these commands.

## Updating my existing installation

Keep a source checkout for development. Before changing the running installation, export memory and take a backup from that installed folder:

```sh
cd "$HOME/Library/Application Support/PersonalAI-Local"
./jarvis export
./jarvis backup
```

From the reviewed source checkout, run tests and use the source-sync helper:

```sh
python3.12 scripts/sync-installed.py
```

It copies authored files and preserves private state, models, browser data, and credentials. It does not remove obsolete source files, install dependencies, migrate data, or rebuild the app for me. Review those needs for each update.

For an update that needs a restart, stop the installed backend and quit the app, update required packages with the installed `.venv/bin/python -m pip`, rebuild native components if changed, and run `./jarvis install` to refresh/reload the LaunchAgent. Reopen the app. Don’t run `install` over an already loaded backend without stopping it first. Preserve the app identity and inspect any new Keychain prompt.

The current copied environment has an old pip-launcher shebang, so use `python -m pip`. A clean environment rebuild is planned. Do not rerun model or SSD initialization as part of a normal source update.
