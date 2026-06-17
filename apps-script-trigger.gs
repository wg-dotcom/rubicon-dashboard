/**
 * Rubicon dashboard — INSTANT update trigger.
 *
 * Fires a GitHub `repository_dispatch` the moment either source sheet changes,
 * so the sync workflow runs immediately instead of waiting for the 15-min cron.
 * It does NOT transform any data — it just says "run now". All the Rubicon
 * filtering / anonymizing / publishing still happens in the GitHub Action.
 *
 * This is a STANDALONE Apps Script (script.google.com → New project) — it
 * installs onChange triggers on both spreadsheets by ID, so you only set it up once.
 *
 * Setup:
 *   1. script.google.com → New project, paste this in.
 *   2. Set GITHUB_TOKEN below (a fine-grained PAT scoped to the rubicon-dashboard
 *      repo with "Contents: Read and write"). Confirm REPO.
 *   3. Run installTriggers() once and approve the Google authorization prompt.
 *   4. Edit either sheet → the dashboard updates within a minute or two.
 *
 *   pingNow() is a manual test you can run to confirm the dispatch works.
 */

// ─── CONFIG ──────────────────────────────────────────────────────────
const GITHUB_TOKEN = 'PASTE_FINE_GRAINED_PAT_HERE';       // Contents: Read and write
const REPO         = 'wg-dotcom/rubicon-dashboard';
const EVENT_TYPE   = 'sheet-changed';
const SHEET_IDS = [
  '1swUUYMpyb5e9zocbONdhqH1ahg53jaQTXM6jyVKXqmc',         // candidates sheet
  '1pKvIJlav4FvYQa4HqOusb0yhfinI-1XaQbESZ-vjMfI',         // open-process tracker
];
const MIN_INTERVAL_MS = 45 * 1000;   // rate-limit: at most one dispatch per 45s
// ─────────────────────────────────────────────────────────────────────

function onSheetChange(e) {
  // Debounce: collapse bursts of edits into one dispatch. The 15-min cron is the
  // backstop that catches any trailing edit skipped by the rate limit.
  const props = PropertiesService.getScriptProperties();
  const now = Date.now();
  const last = Number(props.getProperty('last_dispatch') || 0);
  if (now - last < MIN_INTERVAL_MS) return;
  props.setProperty('last_dispatch', String(now));
  dispatch();
}

function dispatch() {
  const resp = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/dispatches', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'Authorization': 'token ' + GITHUB_TOKEN, 'Accept': 'application/vnd.github+json' },
    payload: JSON.stringify({ event_type: EVENT_TYPE }),
    muteHttpExceptions: true,
  });
  Logger.log('dispatch status: ' + resp.getResponseCode());   // expect 204
  if (resp.getResponseCode() >= 300) Logger.log(resp.getContentText());
}

function installTriggers() {
  // Remove any existing onSheetChange triggers first (idempotent re-install).
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'onSheetChange') ScriptApp.deleteTrigger(t);
  });
  SHEET_IDS.forEach(function (id) {
    ScriptApp.newTrigger('onSheetChange').forSpreadsheet(id).onChange().create();
  });
  Logger.log('Installed onChange triggers for ' + SHEET_IDS.length + ' spreadsheet(s).');
}

function pingNow() { dispatch(); }   // manual test
