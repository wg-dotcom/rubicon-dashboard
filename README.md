# Rubicon × Sagan — Hiring Command Center

A single, private dashboard that centralizes Rubicon's hiring with Sagan:
every open hiring request and the status of every candidate per role.
Live at **https://wg-dotcom.github.io/rubicon-dashboard/** (access code `rubicon2026`).

## What it shows
- **Stat strip** — open roles, open seats, candidates in play, in interviews, roles at offer.
- **Hiring request pipeline** — a kanban (Kickoff → Candidates Presented → Interviewing → Offer/Signature → Placed), one card per requisition, with seats per role.
- **Candidate pipeline** — a 5-stage board, filterable by role, with **video** intro links and **anonymized CV** links.

## Data sources (both sheets, auto-synced)
| Section | Source |
|---|---|
| Hiring requests (status, kickoff, notes) | Sheet 1 — `Core Member's HR` tab, rows where `Company Name = Rubicon` |
| Candidates (board) | Sheet 2 — candidates sheet, rows where `Company Name = Rubicon` |

## Auto-sync — GitHub Action (`.github/workflows/sync.yml`)
Runs on three triggers: **instant** (`repository_dispatch: sheet-changed`, fired by the Sheets trigger below), a **15-min cron backstop**, and manual (**Actions → Run workflow**). It curls both sheets' CSV, runs `build_data.py`, and commits `rubicon-data.json` only when something actually changed. No secrets required for data. (`apps-script-sync.gs` is an alternative; the Action is the active mechanism.)

### Instant updates on sheet edits (one-time setup)
`apps-script-trigger.gs` is a standalone Google Apps Script that pings the workflow the moment either sheet changes, so edits show up in ~1–2 min instead of waiting for the cron:
1. script.google.com → New project, paste `apps-script-trigger.gs`.
2. Set `GITHUB_TOKEN` (fine-grained PAT scoped to this repo, **Contents: Read and write**); confirm `REPO`.
3. Run `installTriggers()` once and approve the Google auth prompt.

It only says "run now" — all Rubicon filtering/anonymizing/publishing still happens in the Action. Edits are debounced (≤1 ping/45s); the cron remains the backstop. Without it, the cron alone keeps things current within ~15 min.

## Privacy — identity protection
The public data ships **only**: first name + last initial, role, location, salary expectation, status, notes, **video** link, and an **anonymized CV** link. It **never** ships emails, phone numbers, raw résumé PDFs, real surnames, addresses, or internal margins (Budget/%WG/Deal Value).

- **Anonymized CVs** live in `cvs/<slug>.html` — clean branded pages (first name only) generated from each résumé. The model returns structured fields; the page is rendered from a fixed template; then a PII audit runs and **any CV that can't be verified clean is left hidden** (fail-safe).
- The access-code gate (`ACCESS_CODE` in `index.html`) is enforced only on the live `github.io` domain (`gateOn`) and is a deterrent, not real security.

### Make CV anonymization automatic (one-time)
The data sync is fully automatic. To also auto-anonymize **new** candidates' CVs each run:
1. Repo → **Settings → Secrets and variables → Actions → New repository secret**.
2. Name `ANTHROPIC_API_KEY`, paste an Anthropic API key.

That's it. On each sync, `anonymize_cvs.py` processes only candidates **not already** in `cv_map.json` (incremental), generates their anonymized page, audits it, and wires the CV button. Without the key, the step is skipped and the rest of the sync still runs. To run the full batch manually: `python3 anonymize_cvs.py cand.csv cvs cv_map.json` (needs `ANTHROPIC_API_KEY`, `pip install anthropic pypdf`).

## Files
| File | Purpose |
|---|---|
| `index.html` | The dashboard. Reads `rubicon-data.json` live; baked-in seed as fallback. |
| `rubicon-data.json` | The data feed (overwritten by the Action). |
| `build_data.py` | Filters both sheets to Rubicon + safe columns → `rubicon-data.json`; merges `cv_map.json`. |
| `anonymize_cvs.py` | Incrementally anonymizes new candidates' CVs → `cvs/*.html` + `cv_map.json`. |
| `cv_map.json` | Map of candidate name → anonymized CV page. |
| `cvs/` | Anonymized CV pages. |
| `.github/workflows/sync.yml` | The scheduled sync + anonymize + commit. |
| `apps-script-sync.gs` | Alternative Apps Script sync (not active). |

## Config (top of `index.html`)
- `ACCESS_CODE` / `GATE_HOSTS` — gate passphrase and where it's enforced.
- `SEATS` — seats (headcount) per role.
- `ROLE_LINKS` — links to each role's full presentation page.
- `MODEL` (top of `anonymize_cvs.py`) — anonymization model; `claude-sonnet-4-6` / `claude-haiku-4-5` to cut cost.
