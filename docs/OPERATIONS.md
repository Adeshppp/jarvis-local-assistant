# Looking after my installation

These notes are for the existing working host. All commands assume I’m in `~/Library/Application Support/PersonalAI-Local`. Don’t treat a fresh clone as if it already has that installation’s private state.

## Configuration

Settings live in `state/config.json`, written privately by `assistant.config.save`. The app can change the conversation/tool models, voice, rate, follow-up interval, and history retention. Other operator settings currently need a reviewed local configuration change and usually a restart.

| Setting | Meaning |
| --- | --- |
| `host` | `127.0.0.1` or explicitly enabled `lan` |
| `model`, `tool_model`, `models` | Selected local models and allowed choices |
| `context`, `max_tokens`, `keep_alive` | Request budget and model residency |
| `retention_days` | Message-age cleanup, currently applied at service startup |
| `filesystem.mode` | Fresh restricted mode or deliberately enabled full mode |
| `filesystem.helper` | Built native file-action helper path |
| `approved_roots` | Named roots for restricted file access and explicit text indexing |
| `applications`, `actions` | Operator-registered app paths and fixed actions |
| `voice` | Wake phrase, voice, timing, and endpoint settings |
| `companions` | Named target-to-device mapping |

Some default voice fields are groundwork rather than a complete device-routing implementation. The web UI can select an enumerated microphone after access is granted; output follows system sound settings. Changing hardware or voice settings needs an actual listening test.

Keep settings exports private even if they contain no token: they can reveal local paths and registered actions. There are no cloud-provider API keys or skill configuration fields yet.

## Models

The running service owns the dedicated Ollama endpoint. Don’t start a second server on the same port. Use the installed CLI with an explicit endpoint for inspection:

```sh
OLLAMA_HOST=127.0.0.1:11435 vendor/ollama/ollama list
./jarvis reload-model
```

Before adding a new model, audit suitable existing internal models and compare official compatibility, licence, memory use, and tool behaviour. The SSD’s capacity does not increase available RAM. Benchmark a candidate before changing the default, and keep only one large model loaded at a time.

Only remove an identifiable downloaded model after checking ownership, other applications’ use, whether it is custom/irreplaceable, and whether its replacement works. Use the runtime’s documented removal command and record the reason and reclaimed space. Do not inspect unrelated SSD content as part of cleanup.

A custom wake phrase uses `./jarvis set-wake '<phrase>' <test.wav>` and must be successfully recognised in the supplied WAV before it is saved. Put that fixture inside the internal project folder. Don’t advertise arbitrary phrase support from a config edit alone.

## Export, backup, and restore

`./jarvis export` writes private JSON containing messages and memories under `exports/`. It is a portable text export, not a complete installation backup. `./jarvis import-memory <file.json>` accepts an explicit file inside the internal project folder, imports text, and does not import executable actions or device credentials.

`./jarvis backup` makes a consistent SQLite snapshot under the bound SSD folder’s `backups/`. This includes the database’s devices, approvals, and other tables, so treat it as private. It does not include the private CA/key files, configuration, Keychain token, model binaries, or volume binding. A complete disaster-recovery plan needs separately secured copies of the right private installation data, and a second physical destination.

For a deliberate restore:

1. Test the procedure on a separate installation first. The production restore drill is still pending.
2. Export and back up the current data, quit the app, and stop the backend with `./jarvis stop`.
3. Copy the chosen known backup from the owned backup folder into a private location inside the internal installation. The restore command refuses outside input paths.
4. Run `./jarvis restore <internal-copy.sqlite3>`. It checks SQLite integrity and makes a before-restore database copy.
5. Run `./jarvis start`, reopen the app, and verify history, memories, device identity, scopes, and a disposable task.

Restoring older device records can invalidate newer pairings or stop a current token matching the restored registry. Keep certificate and credential recovery in the plan; don’t bypass authentication to fix that mismatch. Do not restore while the running service holds SQLite WAL connections.

## Moving the central host later

I want to be able to move the backend to my Mac mini or another Mac. The client/server split supports that direction, but there is no finished migration wizard yet. Check the new host’s architecture, OS, and memory first. Rebuild its environment/native components, migrate data deliberately, update path bindings and server trust, and re-enrol clients as needed. Don’t copy an old virtual environment or forge a drive binding.

## Sleep and shutdown

The MacBook can sleep when the lid closes, so other clients may lose the host. No system sleep or battery protection was disabled. Start/stop controls manage user services, not a permanent always-on machine. Consider a suitable always-on host later rather than silently changing power settings.

## Uninstall

Use the native **Uninstall login services…** command or `./jarvis uninstall`. This stops/removes the project’s matching user LaunchAgents and preserves source, configuration, credentials, memories, and SSD files.

Deleting those remaining files, removing my app’s Keychain entry, removing certificate trust on paired devices, and revoking macOS permissions are separate deliberate steps. A future uninstall wizard should list those choices clearly. Never run a whole-drive cleanup or delete unrelated personal data.
