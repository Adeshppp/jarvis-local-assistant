# Data and permissions in my setup

Jarvis runs with useful access to my computer, so I want its boundaries to be understandable. This is a personal local application, not a hardened multi-tenant service.

## What stays out of Git

`state/` contains my configuration, database, private TLS keys, bootstrap material, browser profile, logs, and undo copies. Pairing files, exports, backups, model weights, and installed third-party binaries also stay local. `.gitignore` covers these, but the actual staged files still need inspection before every publish.

The repository has source, tests, synthetic audio fixtures, and curated documentation. A private GitHub repository does not make committing a live token or private conversation acceptable.

## Device and action permissions

The API uses HTTPS and per-device bearer tokens stored hashed in SQLite. The native app keeps its token in Keychain. Fresh paired devices have limited scopes; the host administrator is separate. Anyone with a device token can act within that token’s scope, so pairing exports must be transferred privately and revoked if lost.

File mutation and sensitive actions use one-use approvals, previews, expiry, and expected-target checks. Browser interactions bind the expected URL. Credential-like file reads require additional approval. These controls still apply when the model proposes an action; natural-language text is not a permission grant from another device.

There is no arbitrary model-generated terminal endpoint. Registered actions and app launches are explicitly configured. A future skill must not bypass this by describing a command in Markdown.

## macOS and storage

Full filesystem mode means on-request access as my normal user, subject to macOS protections. Full Disk Access must be granted by me to the actual backend Python.app. It does not give root privileges. Development should keep using owned fixtures instead of testing against unrelated personal data.

The model process has a separate external-volume sandbox and owned-storage binding. UUID/marker validation stops it using an unrelated replacement drive. ExFAT does not enforce Unix permissions like APFS, so file modes alone do not protect data on a lost external drive. Backups on that drive share its physical risk.

## Network and online data

LAN mode uses private addresses, TLS, and authentication. No public port forwarding or hosted backend was configured. Certificate pins/CA trust must be maintained rather than bypassed when a hostname or certificate changes. Physical client setup is still pending validation.

Web search sends the search query to an external search service; page reading/navigation contacts those websites. Local model inference does not send prompts to an LLM provider. Chromium has a separate profile and does not use my personal Chrome cookies. The public-page/browser tools reject private/local network targets and unsupported credential/upload workflows.

File and web content can contain malicious instructions. Tool validation and approvals provide boundaries, but prompt injection remains an area to evaluate, especially before adding skills or cloud models. Do not treat retrieved instructions as higher authority than my request or the permission checks.

## Future surfaces

GitHub skills need pinned sources, content/dependency review, compatibility checks, controlled execution, and version history. Optional OpenAI/Claude/other provider keys belong in Keychain, with explicit controls for sending project content, visible provider selection, cost limits, and a local fallback. These are roadmap requirements, not current protections for already implemented integrations.

Memory exports, logs, undo files, and backups can contain sensitive text. Review them before sharing. Retention, encrypted backup options, stable distribution signing, and a restore drill remain unfinished work in [the roadmap](../FUTURE_DEVELOPMENT.md).
