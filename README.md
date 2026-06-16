# Rubicon × Sagan — Hiring Command Center

A single, private dashboard that centralizes Rubicon's activity with Sagan:
every open hiring request and the live status of every candidate per request.

## What it shows
- **At a glance** — open roles, candidates in play, in interviews, offers out, placed.
- **Open hiring requests** — one card per requisition with a live mini-funnel and a link to the full Sagan presentation page.
- **Candidate pipeline** — a 5-stage board (Presented → First Interview → Final Interview → Offered → Placed), filterable by role, with one-click resume and intro-video links.

## Files
| File | Purpose |
|---|---|
| `index.html` | The dashboard. Self-contained. Reads `rubicon-data.json` live, falls back to the baked-in seed. |
| `rubicon-data.json` | The data feed. Overwritten by the sync script. |
| `apps-script-sync.gs` | Google Apps Script that filters the candidates sheet to **Rubicon + safe columns only** and pushes `rubicon-data.json` here every 5 min. |

## Data sources
| Section | Source |
|---|---|
| **Open hiring requests** (status, kickoff, notes) | Sheet 1 — the `Core Member's HR` tab of the open-process tracker, rows where `Company Name = Rubicon` (8 live requisitions). |
| **Candidate pipeline** (per-role board) | Sheet 2 — the candidates sheet, rows where `Company Name = Rubicon` (20 candidates). |

## Data & privacy
- The dashboard ships **only Rubicon data, and only customer-safe fields**.
- The `Core Member's HR` tab also holds **Budget ($), %WG and Deal Value ($)** — these internal margin columns are explicitly **dropped** by the sync and never reach this repo.
- A lightweight access-code gate sits in front (`ACCESS_CODE` in `index.html`, currently `rubicon2026`). This is a deterrent, not real security — don't put anything truly sensitive behind it.

## Live updates (the house pattern)
Mirrors `core-dashboard`:
1. Open the **candidates** sheet → Extensions → Apps Script, paste `apps-script-sync.gs`.
2. Set `GITHUB_TOKEN` and confirm `REPO`.
3. Run `pushToGitHub()` once (authorize), then `installTrigger()` for 5-min auto-sync.
4. Update the sheet → dashboard updates itself. No redeploys.

## Deploy
Push this folder to its GitHub Pages repo (e.g. `wg-dotcom/rubicon-dashboard`).
The requisition → presentation-page links in `REQUISITIONS` (top of `index.html`)
assume the existing Rubicon pages are reachable; repoint them to live URLs if needed.

## Config (top of `index.html`)
- `ACCESS_CODE` — the gate passphrase.
- `DATA_URL` — the live JSON path.
- `REQUISITIONS` — open roles + links to each role's full presentation page.
