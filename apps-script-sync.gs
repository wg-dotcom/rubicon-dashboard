/**
 * Rubicon Hiring Dashboard — DUAL-SHEET → GitHub sync
 *
 * Reads BOTH source workbooks and pushes one rubicon-data.json so the dashboard
 * updates automatically whenever the internal team edits either sheet:
 *   1. CANDIDATES sheet  → the candidate pipeline (roles, candidates, statuses)
 *   2. OPEN-PROCESS tracker → hiring-request detail (requirements, target comp)
 *
 * This is a STANDALONE script (not bound to one sheet) so it can read both by ID.
 * Create it at script.google.com → New project, with an account that can open
 * both spreadsheets. Only customer-safe fields ever leave — no margins / %WG / deal value.
 *
 * Setup:
 *   1. Paste this in a new Apps Script project.
 *   2. Set GITHUB_TOKEN + REPO below.
 *   3. Run pushToGitHub() once to authorize (it will ask for Sheets + external-fetch access).
 *   4. Run installTrigger() for a 5-minute auto-sync.
 */

// ─── CONFIG ──────────────────────────────────────────────────────────
const GITHUB_TOKEN   = 'PASTE_YOUR_PAT_HERE';                 // ghp_xxx...
const REPO           = 'wg-dotcom/rubicon-dashboard';         // dashboard repo
const FILE_PATH      = 'rubicon-data.json';
const BRANCH         = 'main';

const CANDIDATES_ID  = '1swUUYMpyb5e9zocbONdhqH1ahg53jaQTXM6jyVKXqmc'; // sheet 2 (pipeline)
const TRACKER_ID     = '1pKvIJlav4FvYQa4HqOusb0yhfinI-1XaQbESZ-vjMfI'; // sheet 1 (open processes)

const CUSTOMER       = 'Rubicon';   // matched case-insensitively, trimmed
// ─────────────────────────────────────────────────────────────────────

/* ============ 1) CANDIDATES SHEET → rows[] ============ */
function readCandidates() {
  const sheet = SpreadsheetApp.openById(CANDIDATES_ID).getSheets()[0];
  const values = sheet.getDataRange().getDisplayValues();
  const head = values[0].map(h => String(h).trim().toLowerCase());
  const col = names => { for (const n of names) { const i = head.indexOf(n); if (i !== -1) return i; } return -1; };
  const idx = {
    batch: col(['batch #','batch']), company: col(['company name']),
    contact: col(['customers name','customer name']), advisor: col(['talent advisor','advisor']),
    role: col(['title/role','role','position']), name: col(['candidates name','candidate name']),
    email: col(['candidates email','candidate email','email']), loc: col(['candidates location','location']),
    salary: col(['salary expectations','salary']), resume: col(['resume link','resume']),
    video: col(['video link','video']), status: col(['status']), notes: col(['notes']),
  };
  const get = (r, i) => (i === -1 ? '' : String(r[i] == null ? '' : r[i]).trim());

  const rows = []; let contact = '', advisor = '';
  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    if (get(row, idx.company).toLowerCase() !== CUSTOMER.toLowerCase()) continue;
    if (!get(row, idx.name)) continue;
    if (!contact) contact = get(row, idx.contact);
    if (!advisor) advisor = get(row, idx.advisor);
    rows.push({
      batch: get(row, idx.batch), role: get(row, idx.role), name: get(row, idx.name),
      email: get(row, idx.email), location: get(row, idx.loc),
      salary: get(row, idx.salary).replace(/[$\s]/g, ''), status: get(row, idx.status),
      resume: get(row, idx.resume), video: get(row, idx.video), notes: get(row, idx.notes),
    });
  }
  return { rows, contact, advisor };
}

/* ============ 2) OPEN-PROCESS TRACKER → requests[] ============
 * Rubicon's open processes live in the flat "Core Member's HR" tab of the tracker.
 * One row per hiring request, with a numbered Status column ("1. KickOff Meeting" …
 * "8. Placed" / "9. Closed / Paused"). We keep ONLY customer-safe columns —
 * Budget ($), %WG and Deal Value ($) are deliberately dropped.
 * Rows are deduped by Hiring Request (HR#), merging notes.
 */
const TRACKER_TAB = "Core Member's HR";

function readTracker() {
  const ss = SpreadsheetApp.openById(TRACKER_ID);
  let sheet = ss.getSheetByName(TRACKER_TAB);
  if (!sheet) sheet = ss.getSheets().filter(s => /core member/i.test(s.getName()))[0];
  if (!sheet) return [];

  const vals = sheet.getDataRange().getDisplayValues();
  const head = vals[0].map(h => String(h).trim().toLowerCase());
  const col = names => { for (const n of names) { const i = head.indexOf(n); if (i !== -1) return i; } return -1; };
  const idx = {
    hr: col(['hiring request']), status: col(['status']), advisor: col(['advisor']),
    company: col(['company name']), role: col(['role']),
    kickoff: col(['alignment date/ kickoff meeting','alignment date / kickoff meeting','kickoff meeting','kickoff']),
    placed: col(['date placed']), notes: col(['notes']),
  };
  const get = (r, i) => (i === -1 ? '' : String(r[i] == null ? '' : r[i]).trim());

  const byKey = {}; const order = [];
  for (let r = 1; r < vals.length; r++) {
    const row = vals[r];
    if (get(row, idx.company).toLowerCase().indexOf(CUSTOMER.toLowerCase()) === -1) continue;
    const role = get(row, idx.role); if (!role && !get(row, idx.hr)) continue;
    const hr = get(row, idx.hr);
    const key = (hr && hr !== 'N/A') ? hr : role.toLowerCase();   // dedupe by HR#, else by role
    const note = get(row, idx.notes);
    if (byKey[key]) {                       // same requisition again (e.g. 2 offers) → merge note
      if (note && byKey[key].notes.indexOf(note) === -1) byKey[key].notes += (byKey[key].notes ? ' · ' : '') + note;
      continue;
    }
    byKey[key] = {
      hr: hr, role: role, status: get(row, idx.status), advisor: get(row, idx.advisor),
      kickoff: get(row, idx.kickoff), datePlaced: get(row, idx.placed), notes: note,
    };
    order.push(key);
  }
  return order.map(k => byKey[k]);
}

/* ============ BUILD + PUSH ============ */
function buildJson() {
  const c = readCandidates();
  let requests = [];
  try { requests = readTracker(); } catch (e) { requests = []; }   // never let the tracker break the sync
  return JSON.stringify({
    updated: new Date().toISOString(),
    customer: CUSTOMER,
    contact: c.contact,
    advisor: c.advisor,
    rows: c.rows,
    requests: requests
  }, null, 2);
}

function pushToGitHub() {
  const json = buildJson();
  const content = Utilities.base64Encode(Utilities.newBlob(json).getBytes());
  const url = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;
  const headers = { 'Authorization': 'token ' + GITHUB_TOKEN, 'Accept': 'application/vnd.github.v3+json' };
  let sha = null;
  const g = UrlFetchApp.fetch(url + '?ref=' + BRANCH, { method: 'get', headers, muteHttpExceptions: true });
  if (g.getResponseCode() === 200) sha = JSON.parse(g.getContentText()).sha;
  const payload = { message: 'Rubicon auto-sync: ' + new Date().toLocaleString(), content, branch: BRANCH };
  if (sha) payload.sha = sha;
  const p = UrlFetchApp.fetch(url, { method: 'put', headers, contentType: 'application/json',
    payload: JSON.stringify(payload), muteHttpExceptions: true });
  Logger.log('Status: ' + p.getResponseCode());
  if (p.getResponseCode() >= 300) throw new Error('GitHub push failed: ' + p.getContentText());
}

function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === 'pushToGitHub') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('pushToGitHub').timeBased().everyMinutes(5).create();
  Logger.log('5-minute trigger installed.');
}
function uninstallTriggers() {
  ScriptApp.getProjectTriggers().forEach(t => { if (t.getHandlerFunction() === 'pushToGitHub') ScriptApp.deleteTrigger(t); });
  Logger.log('Triggers removed.');
}
