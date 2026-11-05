# Working on my Jarvis project

Please read `CHAT_CONTEXT.md`, `ARCHITECTURE.md`, and `FUTURE_DEVELOPMENT.md` before making substantial changes. They are the saved handoff from the original development chat. The code and installed configuration still need checking; a roadmap item is not an implemented feature.

## Keep these decisions intact

- This is a local-first personal assistant. Local chat, speech, history, and memory must remain usable offline after setup.
- I want broad on-request read/search access across my Mac and SSD, and approved file edits/moves/deletes. Do not replace this with an inbox-only runtime policy.
- Setup and development must leave my existing personal SSD data alone. Work in the owned project folder and disposable fixtures; don’t crawl personal files to test search.
- Preserve private state, volume bindings, device permissions, Keychain credentials, TLS material, browser data, and model weights during updates.
- Don’t rerun SSD initialization on the existing installation or create a second top-level SSD folder as a shortcut.
- Don’t disable SIP, Gatekeeper, firewall protections, or TLS checks to get a feature working. No root service or arbitrary LLM shell endpoint.
- New skills and cloud providers must respect the same permissions and explicit privacy choices.

## Source and deployment

The normal private installation is `~/Library/Application Support/PersonalAI-Local`. This Git checkout may be somewhere else. `assistant.config.BASE` and `STATE` are based on the checkout location; there is no universal data-directory environment override.

Run tests in the checkout first. Use `scripts/sync-installed.py` for a reviewed source update to an existing installation, then rebuild/restart only when needed. It intentionally does not copy runtime state or model binaries. Read the update instructions before doing that; repository publication does not itself authorise changing the live installation.

Use `.venv/bin/python -m pip` for packages, particularly on the older copied environment. The native app targets Apple Silicon/macOS 14+. Model downloads are large and belong in bound storage, never in Git.

## Validation and communication

The last full suite passed 75 tests, including the optional real Chromium test. See `docs/TESTING.md` for commands and the difference between synthetic checks and untested physical devices.

Use narrowly relevant tests and disposable fixtures. Some scripts under `scripts/` are live diagnostics that can restart services, change model settings, open apps, or modify their own fixtures. Read them before running them. Do not run every script indiscriminately.

Keep documents natural and personal, as if I wrote them. Explain what changed, what was verified, and what still needs my participation. Ask for real missing input or OS/device approval when necessary, but carry routine authorised work through without repeatedly stopping.

Never commit `state/`, pairing exports, private certificates/keys, `.env` secrets, chats, memories, personal files, a browser profile, or model weights. Check the actual staged files, not just `.gitignore`. Keep machine-specific diagnostics out of the repository unless they have been reviewed and redacted.
