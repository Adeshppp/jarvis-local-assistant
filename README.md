# Jarvis — my local personal assistant

I’m building Jarvis as a personal assistant I can talk to and actually get things done with. It runs on my Mac, keeps its memory locally, and uses models stored on my external SSD. I want to use the same assistant from my other devices without making a cloud service the centre of it.

The goal is simple: ask a question, find a file, open something, make an edit, or look something up online, in a normal conversation.

This is my working personal project. The Mac app and backend work today. Projects, smarter memory, GitHub skills, and optional cloud models are the next stage; they are described in [my development plans](FUTURE_DEVELOPMENT.md).

## What it can do today

- Chat locally using Qwen, with a smaller model for conversation and a larger one for tool requests.
- Listen for “Hey Jarvis,” take a spoken question, and answer using a local voice. Push to talk is available too.
- Keep conversation history and memories I choose to save.
- Search my Mac or attached SSD when I ask, read supported files, and open files or applications.
- Create, edit, rename, move, and delete files, with a preview and approval for changes. Deleting normally means moving to Trash.
- Search the web, read public pages, and open an isolated browser when internet access is available.
- Serve authenticated clients on my private network. A lightweight Mac client and a limited companion agent are included, although my other physical devices still need testing.

There are 18 tools in the current backend. File access is subject to the permissions macOS gives the Python backend. This is more than a chatbot, but it does not have a general terminal tool or unlimited automation of every app.

## Install it

The current build is for Apple Silicon Macs. I’ve tested it on my M1 MacBook Air with 16 GB of memory. The native app targets macOS 14 or later; the actual development machine was running macOS 27.2. Intel Macs and other operating systems have not been validated.

You’ll need Python 3.12, Apple’s command line developer tools, an internet connection for the initial downloads, and the external storage expected by the current installer. The storage initializer is still specific to my 4 TB SanDisk Extreme drive, so this is a source installation rather than a general installer for everyone’s hardware.

Follow [the installation guide](docs/INSTALLATION.md) for the full commands. It covers a new installation and how to update an existing one without replacing its data. **If Jarvis is already working on this Mac, use the update section. Don’t initialize the SSD again.**

The repository contains the complete authored source, native app code, web interface, dependency lock file, scripts, tests, and documentation. It does not contain my chats, saved memories, device tokens, certificates, browser profile, installed packages, model weights, or personal files. Installation creates or downloads those separately.

## Use it

Open `Jarvis.app`, then open Jarvis from the menu bar. Start by typing a question. For voice, click **Wake listening**, allow microphone access when macOS asks, say “Hey Jarvis,” wait for “Yes?”, and then ask your question.

Some things to try:

> Find the notes about my holiday in Documents.
>
> Read this file and tell me what it says: ~/Documents/example.txt
>
> Open Calculator.
>
> Search the web for Python documentation and open it.

For a file edit, Jarvis should show the proposed change and wait for approval. Check the path and preview before approving. Use a disposable file for your first test.

The [user guide](docs/USER_GUIDE.md) explains file access, memory, voice, device pairing, and troubleshooting. A blank window was an early bug; the current native client includes TLS fixes, asynchronous Keychain loading, and connection diagnostics.

## How I’ve set it up

| Part | Current choice |
| --- | --- |
| Mac app | Swift, AppKit, WKWebView, AVFoundation, Keychain |
| Backend | Python 3.12, FastAPI, HTTPS and WebSockets |
| Local inference | Ollama 0.40.14, cloud mode disabled |
| Conversation model | `qwen3.5:2b` |
| Tool model | `qwen3.5:4b` |
| Wake word and transcription | sherpa-onnx keyword spotting and Whisper tiny.en |
| Speech output | An installed local macOS voice |
| History and memory | SQLite; keyword search with FTS5 |
| Browser | Playwright Chromium with its own profile |
| Model storage | One dedicated folder on my external SSD |

Only one language model is kept loaded at a time. Local chat and voice work without internet once the dependencies and models are installed. Web searches and browser navigation need a connection. If the model SSD is disconnected, inference is unavailable until it returns.

## Picking this project up again

I don’t want the next development session to depend on remembering this chat. These are the files to read first:

- [CHAT_CONTEXT.md](CHAT_CONTEXT.md) — what I asked for, what changed, and where the working installation lives.
- [ARCHITECTURE.md](ARCHITECTURE.md) — how the current system fits together.
- [FUTURE_DEVELOPMENT.md](FUTURE_DEVELOPMENT.md) — agreed ideas, unfinished work, and the next priorities.
- [AGENTS.md](AGENTS.md) — practical instructions for an assistant working on the code.
- [Development and testing](docs/DEVELOPMENT.md), [validation notes](docs/TESTING.md), and [security notes](docs/SECURITY.md).
- [Looking after the installation](docs/OPERATIONS.md) — settings, models, backups, restore, host migration, and uninstall.

This repository is a code backup and development home. My live data stays on my devices. I haven’t chosen a public distribution licence yet; third-party models, libraries, and browser binaries keep their own licences.
