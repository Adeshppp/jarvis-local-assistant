# Using my Jarvis

## Start with a normal chat

Open `Jarvis.app` from the installed folder, then use the menu bar icon to open its window. Type a short question and send it. The status/settings area shows which models are configured and whether the backend and SSD are available.

The current interface keeps one main text conversation. History is stored locally and there is keyword history search, but a project sidebar, chat list, and New Chat button are still planned.

## Talk to it

1. Click **Wake listening** and allow microphone access in the macOS prompt.
2. Say “Hey Jarvis.”
3. Wait for “Yes?” before asking the question.
4. Let it finish speaking, then use the follow-up window or say the wake phrase again.

Push to talk is another way to ask. Turn listening off when finished. Voice recognition is English-only in this build. Jarvis pauses its microphone while speaking; speaking over it is not yet a reliable way to interrupt.

The first answer after startup or a model switch can take longer. Ordinary voice questions use the smaller conversation model. A file or browser task can switch to the larger model and include approval steps.

## Files and applications

I’ve enabled full filesystem mode on my own host. That lets Jarvis search and read ordinary files across the Mac and mounted SSD when I ask. macOS can still deny protected paths until the actual backend Python.app has Full Disk Access.

Use a complete path when possible. If you don’t know it, ask Jarvis to search first. Search is bounded and can return partial results; it does not mean every file on the machine was inspected.

Supported reading includes plain text and extraction from PDF, Word, spreadsheets, and RTF, within limits. Scanned PDFs need OCR, which is not implemented. Binary files can be identified or opened without pretending they have readable text.

For changes, inspect the approval card’s action, path, and preview. File edits, creates, moves, deletion, app launches, and browser interactions may need approval. An approval expires and is tied to the expected file/page state. If something changed, ask for a fresh proposal.

Deletion normally uses Trash. Permanent file deletion is a separate explicit approved operation. Do not use important files to test it. Undo copies for edits live privately under `state/file-undo/`; there is not yet a complete undo-management interface.

Registered app/actions are a controlled list, not arbitrary shell access. A remote companion currently supports much less than the host. Name the target device clearly; an offline companion will not cause the action to run on the host instead.

## Memory and history

Use the memory panel to save something useful and remove it with **Forget** when it is no longer wanted. These are global memories in the current version. Saved history and memories are local SQLite data, not GitHub files.

Export from the app or run `./jarvis export` in the installed folder. Export files are private. Keyword document search only covers text explicitly added to the document index; it is separate from on-demand computer file search.

## Internet and the browser

Ask for a web search, a public page, or a browser navigation. Jarvis uses its own visible Chromium session, separate from my personal Chrome login. Reading/navigating a public page is available; filling or clicking requires the relevant approval. Password fields, file uploads, downloads, and private-network administration pages need a different/manual workflow.

Offline, local conversation, memory, supported files, and voice remain available after setup. Web tools report failure rather than inventing online results. Downloading GitHub skills and using OpenAI/Claude keys are future features.

## Useful commands

Run these from the installed folder:

| Command | What I use it for |
| --- | --- |
| `./jarvis status` | Runtime, storage, model, and device status |
| `./jarvis chat 'Hello'` | A quick typed request |
| `./jarvis restart` | Restart the loaded backend service |
| `./jarvis stop` / `./jarvis start` | Stop or start the backend LaunchAgent |
| `./jarvis export` | Private JSON history/memory export |
| `./jarvis backup` | Consistent SQLite backup in owned SSD storage |
| `./jarvis pair <name>` | Create a limited device credential |
| `./jarvis revoke <device-id>` | Revoke a non-admin device |
| `./jarvis lan on` / `./jarvis lan off` | Change LAN mode; restart afterwards |
| `./jarvis uninstall` | Remove login services while preserving data |

`./jarvis --help` lists the other commands. Restore deliberately requires a stopped backend and an input copy inside the internal installation folder. Read the code and keep a separate backup before using it on real data; the production restore drill is still pending.

## If something goes wrong

**Blank or disconnected window:** use the app’s reload/diagnostics controls, check `./jarvis status`, and inspect local `state/logs/server-error.log`. The TLS and Keychain blank-window bugs were fixed, so investigate the actual error rather than disabling certificate checks. Don’t paste raw logs publicly without checking them for personal content.

**File access denied:** check the path, mounted drive, and the backend Python.app’s macOS permissions. Use **File access permissions…** and **Reveal Python app**. Restart after changing Full Disk Access. Don’t grant an unrelated Python build and assume it covers the backend.

**No voice input:** confirm Wake listening or push to talk is active, Jarvis has microphone permission, and the expected system input device is selected. First test typed chat to separate a backend problem from a microphone problem.

**No spoken reply:** check system output/mute and an installed local voice. A microphone or speaker test requires me to be present; a coding assistant cannot hear or speak through my physical devices for me.

**SSD unavailable:** reconnect the bound drive. The monitor checks roughly every ten seconds. Never substitute a different drive with the same name or recreate the binding to suppress an error.

**Slow or wrong answer:** try a narrower request and inspect the actual tool result. A 2B/4B local model has limits. Save a reproducible, redacted example for evaluation instead of assuming successful tool execution proves the explanation is correct.
