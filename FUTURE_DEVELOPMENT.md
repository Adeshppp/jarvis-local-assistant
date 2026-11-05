# What I want to build next

These are the ideas and unfinished jobs from our development chat. An unchecked item is a plan, not something the current app already does. I’ve put the foundations first so the later features have somewhere sensible to live.

## 1. Projects, chats, and smarter memory

I want to create projects in Jarvis, start new chats inside them, and return to old conversations. Each project should have its own memory, with a separate assistant-wide memory for things that apply everywhere.

- [ ] Add projects and named chats to SQLite, with migrations that preserve existing history.
- [ ] Add a project sidebar, New Chat, chat history, rename, archive, delete, and history search.
- [ ] Connect voice requests to the active project/chat rather than a separate hidden device conversation.
- [ ] Keep global preferences across projects and project-specific decisions inside the right project.
- [ ] Let me inspect, correct, pin, export, and forget memories, including their source and scope.
- [ ] Suggest useful memories from chats, with clear review controls and duplicate/conflict handling.
- [ ] Summarise long conversations without losing the original messages or pretending a summary is a quote.
- [ ] Separate chat retention from durable memories and make deletion behaviour clear.

Done when I can create two projects, have several chats in each, reopen them after a restart, and see the right memories retrieved without unrelated project details leaking across.

## 2. Search by meaning

I want to find things even when I don’t remember their exact words.

- [ ] Choose and benchmark a small local embedding model on the M1 host.
- [ ] Add semantic retrieval over chats, global/project memory, and documents I choose to index.
- [ ] Combine keyword and vector results, with filenames, source links, timestamps, and useful snippets.
- [ ] Support incremental indexing, changed/deleted files, cancellation, and index rebuilds.
- [ ] Keep embeddings and caches in owned storage; record the model/version used for each index.
- [ ] Give indexing clear controls. Broad permission to read a file is not a request to silently index my entire SSD.
- [ ] Evaluate retrieval quality using realistic paraphrases and project boundaries.

The existing FTS5 and on-demand filesystem search are useful starting points, but neither is semantic search.

## 3. More reliable task execution

I want Jarvis to understand the task, carry it out, check the result, and tell me what really happened.

- [ ] Add a plan → act → verify workflow for tasks that need several steps.
- [ ] Show progress and an understandable action trace; distinguish proposed, waiting, running, completed, and failed steps.
- [ ] Read back edited content and verify other outcomes before claiming success.
- [ ] Improve retries and recovery for unavailable models, expired approvals, changed files, offline targets, and failed websites.
- [ ] Add resumable jobs for longer tasks, with cancellation propagated through backend/model/browser work.
- [ ] Improve tool selection and argument accuracy, especially when a small model guesses a path.
- [ ] Add evaluations for natural-language file tasks, grounded answers, prompt injection, and refusal/permission mistakes.
- [ ] Review timeouts and the current six-turn tool-loop limit against realistic tasks.

## 4. Useful context and reusable workflows

- [ ] With my permission, use the active application, selected text, or a file I’m working on as context.
- [ ] Add explicit screenshot/screen-reading support only when needed, using the required macOS permissions.
- [ ] Make it obvious which context is being used and let me turn it off.
- [ ] Let me save a successful sequence as a named workflow and run it later.
- [ ] Remember my corrections as reviewed instructions or workflow preferences, rather than silently retraining model weights.
- [ ] Build real Shortcuts/AppleScript or n8n integrations where useful; the current registered-action framework is only groundwork.

## 5. Skills from GitHub

I want to paste a GitHub skill link and have Jarvis keep it locally, understand when it is useful, and use it later. I shouldn’t have to remember the names of all installed skills.

- [ ] Accept repository, folder, and supported `SKILL.md` links; resolve them to a pinned commit.
- [ ] Download instructions, references, and assets into an owned local skills directory.
- [ ] Keep a searchable catalogue with name, description, source, commit, licence, required tools, dependencies, and global/project scope.
- [ ] Match requests to installed skills automatically, using metadata and eventually semantic search.
- [ ] Load the chosen skill’s instructions when needed rather than placing every installed skill into every prompt.
- [ ] Check whether a skill expects tools or services Jarvis does not have; explain missing capabilities before promising to use it.
- [ ] Support enable/disable, removal, update previews, version rollback, and conflicts between skills.
- [ ] Review new executable scripts and dependency changes before first execution. Stage work in an isolated working area with explicit inputs and outputs.
- [ ] Keep file approvals, device permissions, and cloud/privacy rules in force. A downloaded instruction cannot grant itself access or turn on arbitrary shell execution.
- [ ] Show which skill is being used and keep its source/version with the task record.

The [Agent Skills specification](https://agentskills.io/specification) and [client implementation guide](https://agentskills.io/client-implementation/adding-skills-support) are useful starting points. Compatibility needs implementation and tests; downloading a Markdown file alone does not add missing tools or improve the base model’s reasoning.

## 6. Look for a skill online when I give it a task

I asked for internet-first skill discovery when a connection is available. The intended experience is to look for a useful skill at the start of a new task, compare it with what is already installed, and then do the work. Reusing that choice for follow-up messages should avoid an unnecessary search on every sentence.

- [ ] Detect whether online discovery is available, with a short timeout and a clear offline fallback.
- [ ] Search for relevant skills using a generic task description, without sending private chats or file contents as search queries.
- [ ] Prefer compatible, maintained sources; inspect the content, dependencies, licences, and pinned version.
- [ ] Reuse a suitable local skill when discovery adds nothing, and cache useful results for offline work.
- [ ] Keep discovery separate from executing newly downloaded code. New scripts/dependencies still need review.
- [ ] Explain when no suitable skill is found and continue with the assistant’s existing tools where possible.
- [ ] Add settings for online discovery, source preferences, and how much searching a task should do.

## 7. Other LLMs when internet is available

I also want an option to add API keys for OpenAI, Claude through Anthropic, and other LLM providers. Local models should remain the default and work offline.

- [ ] Add a provider abstraction so the conversation/tool loop can use local or remote models without duplicating policy checks.
- [ ] Store API keys in macOS Keychain, with add, test, replace, and remove controls. Never write keys to Git, ordinary config exports, or logs.
- [ ] Let me choose a provider/model per task or project and see when a request is leaving my Mac.
- [ ] Require a clear choice before sending personal file content, history, or memory to a cloud provider; give each project its own controls.
- [ ] Add cost estimates where available, budgets, rate limits, timeouts, cancellation, and usage history.
- [ ] Handle provider-specific tool formats and errors, and test them with mocked responses before live calls.
- [ ] Offer a clear local fallback if the internet/provider fails, without silently switching privacy or billing modes.
- [ ] Research current official provider SDKs, model availability, terms, and pricing at implementation time.

No cloud keys, provider SDK integration, or automatic cloud fallback are configured in this version.

## Other work I don’t want to lose track of

### Installation and day-to-day reliability

- [ ] Build a proper setup/update wizard, including choosing supported storage rather than hardcoding my SanDisk model.
- [ ] Recreate the deployed virtual environment cleanly; the copied environment’s standalone pip launcher can point to an old path.
- [ ] Make downloads resumable and checksum-verified, including interrupted speech-model extraction; don’t solve failures by overwriting existing data.
- [ ] Improve model/storage discovery and portability of configuration paths.
- [ ] Make central-host migration to the Mac mini or another Mac repeatable, including data, model paths, certificates, and client re-enrolment.
- [ ] Consider a small internal fallback for SSD absence, with a clear degraded-mode indicator.
- [ ] Test an actual logout/login cycle and long-running launchd recovery.
- [ ] Physically unplug/reconnect the SSD during a controlled fixture-only test.
- [ ] Run a documented restore drill against a separate test installation before relying on production recovery.
- [ ] Add backup rotation, optional encryption, and log/undo/browser-data retention controls. Backups on the same SSD do not protect against losing that drive.
- [ ] Improve the device permissions interface, certificate renewal/network-change handling, and revocation visibility.
- [ ] Finish the settings experience for tool policies, startup, approved/indexed locations, storage use, and wake-phrase validation; some controls currently need the CLI or a local config edit.
- [ ] Add stable signing/notarisation and a packaged installer if I decide to distribute the app.
- [ ] Make uninstall/data-removal choices clear without deleting personal data by default.
- [ ] Decide on a distribution licence before making this a public open-source release.

### Voice and devices

- [ ] Measure actual microphone → answer latency and false wake rates in my room.
- [ ] Add reliable interruption while speaking, echo handling, speaker/microphone selection, and noise-tolerant endpointing.
- [ ] Evaluate multilingual speech and more natural local voices within the memory budget.
- [ ] Check the Mac mini’s processor/OS and install/test the lightweight client on the actual device.
- [ ] Test iPhone certificate enrolment, authentication, foreground microphone, local speech, and network reconnects on the real phone.
- [ ] Decide whether a native iPhone app or Siri Shortcut is needed for background access; don’t promise always-listening iOS behaviour from a web page.
- [ ] Set up optional private remote networking such as Tailscale only if requested; no public port forwarding by default.
- [ ] Expand companion tools deliberately, with permissions on the target Mac and no silent host fallback.

### File tools, performance, and quality

- [ ] Add OCR, chunked large-document reading, richer Office edits, and better format coverage.
- [ ] Improve file search ranking, cancellation, accessibility feedback, and handling of partial results.
- [ ] Broaden real-application integration tests using disposable fixtures; retain stale-file and wrong-target checks.
- [ ] Measure memory pressure, thermals, CPU/GPU use, battery impact, model-switch cost, and a longer stability soak.
- [ ] Test new local models against actual tool tasks before replacing the current models.
- [ ] Add repeatable macOS CI, with optional explicit downloads for Chromium integration tests.
- [ ] Review the Starlette TestClient/httpx deprecation warning before the next dependency upgrade.
- [ ] Review security at each new surface: retrieved documents, browser text, skills, executable dependencies, and cloud routing.

My preferred next step is the projects/chats/memory foundation, then semantic search. That gives skills, workflows, and cloud routing a clearer place to attach.
