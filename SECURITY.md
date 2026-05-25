# Security Policy

## Supported versions

ProxyBox is in active development. Fixes land on `main` and are tagged into the next release. Production deployments should track the latest tag.

| Version | Supported |
| --- | --- |
| latest tagged release | ✅ |
| older tags | ❌ — please upgrade |

---

## Reporting a vulnerability

Please **do not open a public GitHub Issue** for security reports. A public issue is readable by everyone the moment it is posted, which is not what you want for an unfixed problem.

Instead, use GitHub's private vulnerability reporting:

➡️ **<https://github.com/carlos0xx/proxybox/security/advisories/new>**

This opens a private channel with the maintainer, kept inside GitHub until a fix is ready. No email addresses are exposed on either side.

### What to include

A useful report has:

- **Affected component** — installer, admin API, traffic worker, bot, SPA, or the sing-box config writer.
- **Affected version(s)** — the install tag.
- **Pre-conditions** — does it require an authenticated session, local network access, or nothing at all?
- **Reproduction** — the minimum steps that show the problem.
- **Suggested fix**, if you have one.

### Response targets

ProxyBox is a small-team project. Realistic timelines:

| Stage | Target |
| --- | --- |
| Acknowledge receipt | within 72 hours |
| Initial assessment | within 7 days |
| Fix on `main` for confirmed high-severity reports | within 30 days |
| Public advisory | once the fix ships in a tagged release |

Lower-severity hardening may be bundled into a regular release without a separate advisory.

---

## Out of scope

These are not ProxyBox issues (report upstream where relevant):

- Bugs in `sing-box`, `caddy`, `fail2ban`, or `python-telegram-bot`.
- Reports that assume the reporter already has root or read access to `/etc/proxybox/`. At that point the host is already compromised.
- A weak password that the operator set manually. The default 16-character random password is fine; overriding it with something weak is the operator's choice.
- Load-based denial of a publicly exposed `:8080`. Front the panel with Caddy and a firewall if you expose it openly.
- Issues in third-party client apps (Shadowrocket, Stash, Clash Verge, etc.).

---

## Credit

Reporters who privately disclose valid issues will be credited (with consent) in the advisory and in `CHANGELOG.md`.

---

## See also

- [`CONTRIBUTING.md`](./CONTRIBUTING.md) · non-security contributions
- [`docs/architecture.md`](./docs/architecture.md) · the threat model and what the project deliberately does not defend against
