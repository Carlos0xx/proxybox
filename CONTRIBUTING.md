# Contributing to ProxyBox

Thanks for your interest. ProxyBox is a small, focused project — every PR gets read by the maintainer personally.

## Quick links

- **Bug?** Open a [bug report](https://github.com/carlos0xx/proxybox/issues/new?template=bug_report.yml).
- **Feature idea?** Open a [feature request](https://github.com/carlos0xx/proxybox/issues/new?template=feature_request.yml) **before** writing code — saves you the round-trip if the idea doesn't fit.
- **Security issue?** **Don't open a public issue.** Follow [`SECURITY.md`](./SECURITY.md).
- **Doc typo / small fix?** Just open a PR directly.

---

## Development setup

```bash
git clone https://github.com/<your-fork>/proxybox && cd proxybox
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

That's it — one FastAPI app + one Telegram bot + one single-file SPA. No build step for the front-end.

### Tests

```bash
pytest -v tests/
```

### Linters

```bash
ruff check app/ bot/
ruff format --check app/ bot/
```

`ruff` (config in `pyproject.toml`) is the single source of truth for Python style — no separate `black` / `isort`.

---

## Pre-commit hook

The repo ships a pre-commit hook that runs `scripts/pii-check.sh` on staged files. Enable once per clone:

```bash
git config core.hooksPath .githooks
```

It blocks accidental PII (home-directory paths, real hostnames, etc.). The pattern list lives in `~/.proxybox-pii-blocklist.txt` — create one for your environment; see the `scripts/pii-check.sh` header.

---

## Commit message style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <short summary>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `security`, `ci`, `build`, `chore`. See `git log --oneline` for examples.

---

## Pull request flow

1. **Fork** on GitHub.
2. **Branch** from `main`: `git checkout -b feat/your-feature`.
3. **Commit** with the convention above.
4. **Push** to your fork and **open a PR** against `carlos0xx/proxybox:main`.
5. **CI runs** automatically (lint, test, gitleaks, secrets-scan, build) — all must be green before merge.
6. The maintainer reviews; push more commits to iterate.

---

## Code quality bar

- Public APIs (routes, exported functions) get a one-line docstring.
- No unexplained `# noqa`, `# type: ignore`, or `subprocess(shell=True)` — add a comment if you must.
- New behaviour gets a test; bug fixes get a regression test.
- No new runtime dependency without a paragraph justifying it.
- PII discipline: no real IPs, domains, device names, or tokens in code or commit messages. CI runs `pii-check.sh` + `gitleaks`.

---

## What we'll probably say no to

To set expectations honestly:

- **Front-end framework rewrites** (React/Vue/Svelte). The SPA is one HTML file on purpose — no build step, no `node_modules`.
- **Cloud control planes / SaaS dashboards.** The project is self-hosted only.
- **Telegram bot features that aren't replicas of admin-UI actions.** The bot is opt-in mobile convenience, not a full admin surface.

If you're unsure whether a change fits, open an Issue first.
