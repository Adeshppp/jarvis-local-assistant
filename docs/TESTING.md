# What I’ve checked

These notes separate automated/fixture checks from things that still need real hardware testing. The recorded development baseline is 5 November 2026, version 0.2.0.

## Regression suite

```sh
.venv/bin/python -m pytest -q
```

Without browser assets, expect the Chromium integration test to skip. To include it, install Chromium in an ignored local directory and point the test at it:

```sh
PLAYWRIGHT_BROWSERS_PATH="$PWD/state/browser-binaries" \
  .venv/bin/python -m playwright install chromium
JARVIS_BROWSER_BINARIES="$PWD/state/browser-binaries" \
  .venv/bin/python -m pytest -q
```

The full baseline passed **75 tests**. Coverage includes authentication, TLS certificate usage, SSD identity/path boundaries, memory/history, device/companion routing, per-device tools, approvals, personal-file operations, stale targets, and grounded tool responses.

The repository-preparation rerun also passed all 75 tests in about 26 seconds. It emitted one upstream Starlette warning about TestClient's httpx integration; there were no test failures. Review that dependency compatibility during the next package update.

The real-browser case visits public pages, injects a synthetic form into the test page, and verifies approved fill/click, blocked password handling, and rejection after page navigation. It uses no personal login or existing browser profile. This test needs network access; the remaining tests are the normal lightweight starting point.

Two included WAV files are synthetic spoken fixtures created for testing. They are not recordings of my microphone or private conversations.

## Functional checks from the build

- Missing/wrong API tokens were rejected; intended device scopes were enforced.
- HTTPS certificate chain, server-authentication usage, and native validation were checked.
- Supported file reading, previews, edits, move/open, native Trash, and explicit permanent-file deletion were exercised on newly created fixtures.
- A protected Documents fixture was read after I enabled Full Disk Access for the backend Python.app.
- SSD writes stayed inside the newly owned assistant folder during development tests.
- Natural-language file discovery and a 4B-model answer returned the actual fixture content rather than a guessed path or a metadata-only claim.
- Web search, a public Python documentation page, and visible browser navigation worked.
- Wake-word/transcription/answer flow worked with synthetic audio, including the follow-up/cancel paths checked by diagnostics.
- Launchd bootstrap/restart/recovery and simulated storage identity loss/reconnect were exercised.
- A consistent SQLite backup was created and checked.

These checks support the specific workflows tested. They do not prove every application, file format, website, or natural-language request works.

## Measurements on the M1 host

| Measurement | Conversation model | Tool model |
| --- | --- | --- |
| Model | `qwen3.5:2b` | `qwen3.5:4b` |
| Observed resident model memory | About 3.26 GB | About 4.38 GB |
| Warm generation | About 21 tokens/second | About 15 tokens/second |
| Warm first token | About 0.21 seconds | About 0.32 seconds |
| Cold first token in sampled run | About 9.23 seconds | About 8.16 seconds |

These are snapshots, not guaranteed latency. Only one model is loaded at a time. Sampled swap use was zero, which is not a long-term memory-pressure assessment. A natural file-read task with the tool model took about 22 seconds end to end. Synthetic ordinary voice requests measured roughly 6.4–7 seconds; that is not a measured acoustic microphone-to-speaker result.

## Still needs testing

- Actual Mac mini client and companion on its real processor/OS.
- Actual iPhone enrolment, authentication, microphone, local speech, and reconnection.
- A real logout/login cycle.
- Physical SSD detach/reconnect while the service is running.
- A restore drill on an isolated installation, followed by a deliberate production recovery plan.
- Real-room wake reliability, acoustic latency, device routing, and interruption.
- Longer stability, thermal, battery, and memory-pressure measurements.

The native window’s platform diagnostics and user use indicated it was loading after the TLS/Keychain fixes. Automated visual control of the Jarvis app was not available in that development session; don’t describe a complete visual UI test as having passed.

Raw local diagnostic reports can include machine addresses, file paths, bindings, or task text. They were intentionally left out of this repository. If I add results later, they need a review/redaction pass first.
