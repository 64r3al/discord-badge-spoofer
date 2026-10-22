# Development Roadmap

This roadmap prioritizes safety, transparency, maintainability, and testability before feature work.

> **Platform notice:** This project interacts with undocumented Discord analytics endpoints and may violate Discord's Terms of Service. Endpoints can change, and account restrictions are possible. Do not use an account you cannot afford to lose. This project is not affiliated with Discord.

## Phase 1 — Security and reliability

- [ ] Keep `science_state.json` and all credential-bearing files out of version control. The existing `.gitignore` should continue to exclude them.
- [ ] Replace plain-text token/cookie storage with an operating-system credential store where practical. Until then, clearly warn users that the state file contains secrets and never print credentials.
- [ ] Add a command to clear locally stored credentials and state safely.
- [ ] Add an explicit network-destination allowlist and automated tests proving that authorization tokens and cookies are never sent to third-party hosts.
- [ ] Make any non-Discord metadata lookup optional and document exactly what is sent to each host.
- [ ] Redact authorization headers, cookies, analytics tokens, and fingerprints from logs and error messages.
- [ ] Fail closed on authentication errors, permission errors, unexpected response formats, or unknown destinations.

## Phase 2 — Testability

- [ ] Add unit tests with mocked HTTP responses; tests must not contact Discord or send real activity events.
- [ ] Cover malformed input, missing state, expired cached data, network failures, HTTP errors, and interrupted execution.
- [ ] Add a dry-run mode that previews the intended request structure without credentials or network calls.
- [ ] Validate user inputs and provide clear, actionable error messages.
- [ ] Add regression tests for every security issue fixed.

## Phase 3 — Maintainable codebase

- [ ] Split the single script into focused modules (CLI, configuration/state, networking, data models, and diagnostics).
- [ ] Add `--help`, `--version`, and consistent exit codes.
- [ ] Separate display/progress reporting from application logic.
- [ ] Use predictable timeouts, bounded retries, and respectful rate-limit handling; never keep retrying authentication or forbidden responses.
- [ ] Document supported Python versions, setup, expected files, limitations, and troubleshooting.

## Phase 4 — Automated quality checks

- [ ] Add GitHub Actions to run unit tests and static checks on each pull request.
- [ ] Add linting and type checks, and review security-relevant changes before release.
- [ ] Publish a changelog and verify release artifacts against the reviewed source revision.
- [ ] Add a security reporting process and instructions for reporting vulnerabilities without publishing secrets.

## Engineering principles

1. **No secret collection or telemetry.** Never add analytics, webhooks, remote logging, or credential uploads.
2. **No secrets in Git.** Never commit tokens, cookies, local state, logs, or real account data.
3. **Transparent networking.** Every network destination must be documented and covered by tests.
4. **Safe tests by default.** Automated tests use mocks and never send real activity events.
5. **No evasion features.** Prioritize code quality and account security rather than bypassing platform safeguards or hiding activity from enforcement systems.
