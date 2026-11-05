# Working on the code

I keep the source in Git and the running installation in Application Support. They can be separate copies. A source edit is not a deployment, and a repository sync should not overwrite the live data.

Start with `CHAT_CONTEXT.md` and `AGENTS.md`. The important boundaries are the owned SSD storage API, full on-request personal-file tools, per-device scopes, and one-use approvals.

## Local environment

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pytest -q
```

This does not require downloading the language or speech models. The optional real-browser test needs Chromium and internet; see [TESTING.md](TESTING.md). Keep a development checkout separate from private production state. Configuration paths currently derive from the package location, so copying state into a checkout is not a harmless setup shortcut.

Build the native app with `scripts/build-mac.sh` on Apple Silicon. It compiles the file-action helper and Swift app, creates a local bundle, and ad hoc signs it. A build does not itself install launch services.

## Before changing behaviour

Check the relevant schemas and the device/approval path, not just the model prompt. Untrusted file, browser, and future skill text must not acquire authority to run tools. Any change to file mutation needs stale-target, scope, preview, approval, and outcome checks.

Database changes need a migration plan and a backup. Projects, chats, memory scopes, embeddings, skills, and provider routing will all touch persistent state. Add them deliberately rather than replacing the existing database.

Update `requirements.lock` when dependencies change and review the diff. Don’t bundle downloaded third-party code, model weights, native binaries, a virtual environment, or a browser profile into Git.

## Script map

| Script | Purpose |
| --- | --- |
| `build-mac.sh`, `build-file-actions.sh` | Local native builds |
| `serve-models.py` | Foreground model server using the owned-storage sandbox/environment |
| `download_speech.py` | First-time official speech-asset download/extraction |
| `sync-installed.py` | Copy reviewed authored files to an existing private install |
| `prepare-devices.py`, `build-remote-client.py` | Generate local enrolment materials/client bundle |
| `check-native-tls.swift`, `check-seatbelt.py` | Focused platform diagnostics |
| `smoke.py`, `access_smoke.py`, `natural_requests.py` | Live API/tool checks using generated fixtures |
| `benchmark.py`, `stability.py`, `reliability.py` | Live measurements and recovery exercises |
| `registered-diagnostic.py` | Example registered-action diagnostic |

Read a live diagnostic before running it. Some change settings, open a browser/app, use a microphone fixture, or stop/restart processes. Run only what the change needs. Tests must use created fixtures, including on the SSD, not existing personal files.

## Deploying a reviewed update

Use the update section of [INSTALLATION.md](INSTALLATION.md). Back up/export first. The sync helper copies authored files but does not remove obsolete files, apply database migrations, install new dependencies, or build the app. Handle those deliberately, with the backend stopped when needed.

For the current older installed environment, run package commands through `.venv/bin/python -m pip`; the copied standalone pip launcher may have an old shebang. Native identity and certificate/Keychain changes can affect permissions, so keep them stable unless the change requires otherwise.

After a deployment, check status, a short chat, and a disposable relevant tool action. Update these docs when behaviour changes. Keep pending physical tests marked pending until someone actually performs them.
