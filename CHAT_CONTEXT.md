# Where I left Jarvis

Last updated: 5 November 2026. This is the handoff I want available when I come back to the project, including when a different coding assistant reads the repository. It records decisions and useful context from the development chat, without copying private credentials or my conversation database into Git.

My development repository is [Adeshppp/jarvis-local-assistant](https://github.com/Adeshppp/jarvis-local-assistant). I explicitly asked for it to stay private.

## What I’m trying to build

I want a personal assistant that runs locally, talks naturally, remembers useful things, and can help with real tasks on my computer. My MacBook Air is the main host. I also want to use it from my Mac mini and iPhone, with the heavy inference staying on the main machine.

Local processing and ownership of my data matter to me. Internet access is useful for research, browsing, finding skills, and eventually using other LLM providers when I choose. It should still be useful offline.

## The most important clarification from the chat

My original setup request put strict restrictions on the external SSD: create one new project folder and don’t inspect, change, or interfere with my existing SSD data. Those restrictions applied to building and maintaining the assistant.

Later I clarified what I want **Jarvis itself** to do: when I ask, it should be able to search and read across my computer and SSD, open files and apps, edit content, move files, and delete files. I do not want a read allowlist limited to an inbox. Changes still have previews and approvals, and macOS permissions still apply.

These are two separate decisions that both remain valid. During development, use the project’s own files and disposable fixtures. During an authorised Jarvis task, use the broad runtime file access I requested. Don’t undo the latter because of the older setup restriction.

## What happened during the build

1. The host was checked, existing local model locations were audited, and a new owned folder was allocated on the external SSD. The setup used drive metadata instead of browsing existing SSD contents.
2. A Python backend, private HTTPS API, SQLite memory/history, local model runtime, voice pipeline, and Swift menu bar app were built.
3. The installation moved from Documents into Application Support because a launchd service could not reliably read the earlier Documents location under macOS privacy controls.
4. The app initially opened with a blank window. The local TLS certificate needed the server-authentication extension and a proper private CA chain. Keychain retrieval also needed to happen asynchronously so it could not hold up the window. Both were fixed, and diagnostics/retry behaviour were added.
5. I tried the assistant and wanted broader tools. Full Mac and SSD file operations and real web/browser tools were then implemented.
6. I personally enabled Full Disk Access for the backend’s Python.app. A protected Documents fixture was then read successfully. That permission belongs to this Mac installation; a clone won’t inherit it.
7. The smaller model sometimes invented file paths or claimed it could only see metadata even after a successful read. Tool-result grounding was improved, and file/browser requests were routed to the 4B model. Natural-language file discovery and web navigation were checked again.
8. I asked about smarter memory, projects, chat history, semantic search, more reliable task execution, contextual awareness, workflows, and GitHub skills. These remain planned, not shipped.
9. I asked for this repository, readable documentation, a full handoff, and a roadmap that also includes optional OpenAI, Claude, and other API-based models when online.

## The working installation

| Item | Location or setting |
| --- | --- |
| Installed backend and source | `~/Library/Application Support/PersonalAI-Local` |
| Native app | `~/Library/Application Support/PersonalAI-Local/Jarvis.app` |
| Private configuration and database | The installed folder’s `state/` directory |
| Model/project storage | `/Volumes/Sandisk/Personal_AI_Assistant` |
| Backend LaunchAgent | `local.personal-ai.server` |
| Desktop LaunchAgent | `local.personal-ai.desktop` |
| HTTPS API | Port 8765 on loopback, plus private LAN addresses when enabled |
| Local model API | `127.0.0.1:11435` |
| Project version | `0.2.0` |

The SSD binding also has a volume UUID and a marker ID. Those live only in private state and on the SSD. Do not reconstruct them from this document. The storage initializer refuses to reuse a binding and must not be rerun on the existing installation.

The original development copy was under the Codex task’s `outputs/PersonalAI` folder. This repository was prepared separately as `outputs/jarvis-local-assistant`, without copying runtime state. For new work, use the Git checkout as the maintained source and deliberately sync reviewed changes to the installed copy. Editing the checkout does not automatically update the running app.

The current host is an M1 MacBook Air, 16 GB unified memory, Apple Silicon, running macOS 27.2 at the time of development. The internal drive is 500 GB. The external drive is a 4 TB SanDisk Extreme 55DD, formatted ExFAT. My Mac mini has 8 GB of memory; its processor and OS still need checking. The iPhone OS and physical client behaviour also remain unverified.

## Current configuration worth preserving

- Conversation model: `qwen3.5:2b`; tool model: `qwen3.5:4b`. Both downloaded locally.
- Deployed context: 6,144 tokens; answer limit: 320 tokens; model keep-alive: three minutes.
- One loaded model and one model request at a time. Runtime cloud mode disabled.
- Runtime: the official Ollama 0.40.14 macOS archive. The Homebrew Ollama installation did not work on the host’s macOS version during setup.
- Full filesystem mode is enabled in the installed configuration. A brand-new `defaults()` configuration deliberately starts restricted until the operator changes it.
- The native file helper is installed at `vendor/file-actions`.
- LAN access is enabled on the host, with TLS, authentication, per-device permissions, and private IPv4 bindings. No public wildcard listener or router forwarding was configured.
- Chromium is visible and uses Jarvis’s own profile, not my personal Chrome profile.
- Voice currently uses English models, a “Hey Jarvis” keyword detector, an eight-second follow-up window, and local macOS speech output. The microphone is paused during speech to avoid hearing itself.

The backend runs as my normal user so approved file tools can use Full Disk Access. The separate model process still receives a sandbox profile restricting its external-volume access to the owned project folder. Don’t put the full-access backend back under the old blanket SSD sandbox: that would break the runtime access I asked for.

There is a deployment wart: the existing virtual environment was copied during the move, so its standalone `pip` launcher can contain an old shebang. Use `.venv/bin/python -m pip`. Recreating a clean environment is a maintenance item, not something to do silently during repository publication.

## What is implemented and what isn’t

There are real file and browser tools, scoped devices, approval records, local global memory, persistent messages, keyword history search, explicit text-document indexing, backups, and a small remote companion framework.

There is no project entity, project memory, New Chat UI, chat list, embedding model, semantic retrieval, skill installer/catalogue, automatic skill discovery, cloud-provider routing, or self-training system yet. The UI currently uses a fixed `main` text conversation. Voice sessions use their own device conversation. The database’s conversation field is groundwork, not a finished chat product.

The secondary Mac companion currently exposes system information and explicitly enabled simple app launches. It does not mirror all host file tools. Tailscale, Siri Shortcuts, a native iPhone app, and production n8n/Shortcuts workflows were not set up. Registered actions have a framework and diagnostic example, not a library of ready-made integrations.

## How much has been checked

The automated suite passed 75 tests, including a real Chromium test with a synthetic form. Functional checks covered authenticated APIs, owned file fixtures, approvals, file extraction, native file actions, public web search/page reading, and natural-language tool requests. Test records and practical limits are in [docs/TESTING.md](docs/TESTING.md).

Physical Mac mini and iPhone tests are still pending. So are an actual logout/login test, a physical SSD disconnect/reconnect test, a production restore drill, and a measured real-microphone/acoustic latency test. A simulated storage failure/recovery passed; that is not the same as physically unplugging the drive. Don’t turn these into completed claims in future docs.

## How I like to work on this

I prefer the assistant to carry useful work through without repeatedly asking me to confirm routine steps. Tell me clearly when my participation is actually needed, such as a macOS permission prompt, speaking into the microphone, or testing a physical device.

Keep explanations short in chat. Write documentation in a natural, personal voice rather than marketing language. Don’t call a planned feature finished. Don’t change system security settings or scan my personal SSD files as a development shortcut. I initially asked to use Chrome for GitHub. Computer-use access remained blocked, so I explicitly authorised the GitHub CLI instead and completed its browser sign-in myself. The repository must remain private.

No repository should contain live tokens, private keys, my browser data, private chats, raw microphone recordings, or personal documents. A private repository is still not the place for those.

## Where to start next time

Read this file, [ARCHITECTURE.md](ARCHITECTURE.md), and [FUTURE_DEVELOPMENT.md](FUTURE_DEVELOPMENT.md). Check the actual installed status and compare source before deploying. Preserve state, SSD binding, Keychain identity, and device permissions. The first feature priority is the projects/chats/memory foundation, followed by semantic search; skills and optional cloud providers should build on that foundation.
