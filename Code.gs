/**
 * Training guide — Google Sheet + Calendar backend.
 *
 * Paste into Extensions → Apps Script of the Google Sheet, set TOKEN,
 * then Deploy → New deployment → Web app (Execute as: Me, Who has access: Anyone).
 * Put the web app URL and the same TOKEN into the app (bottom of any tab → Sync).
 *
 * Tabs it creates in the sheet:  Log · Plan · State
 * Calendar it creates:           "Training" (a separate layer in your Google Calendar)
 */

const TOKEN = 'CHANGE-ME';          // any long random word; the app must send the same
const CAL_NAME = 'Training';
const TZ = 'Europe/Oslo';
const REMINDER_MIN = 30;

const LOG_HEAD  = ['id','date','time','tab','section','exercise_id','exercise','slot','slot_name','dose','result','completed','seconds','feel','note','logged_at'];
const PLAN_HEAD = ['id','date','start','minutes','title','tab','items','event_id','status','created_at'];

/* ---------- entry points ---------- */
function doGet(e)  { return handle_(e && e.parameter || {}, null); }
function doPost(e) {
  let body = {};
  try { body = JSON.parse(e && e.postData && e.postData.contents || '{}'); } catch (err) {}
  return handle_(e && e.parameter || {}, body);
}

function handle_(query, body) {
  const req = Object.assign({}, query, body || {});
  if (!TOKEN || TOKEN === 'CHANGE-ME') return out_({ ok: false, error: 'Set TOKEN in Code.gs first' });
  if (req.token !== TOKEN) return out_({ ok: false, error: 'Wrong token' });
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    switch (req.action) {
      case 'ping':      return out_({ ok: true, sheet: SpreadsheetApp.getActive().getName(), calendar: CAL_NAME });
      case 'log':       return out_(logRows_(req.rows || []));
      case 'update':    return out_(updateRow_(req.id, req.fields || {}));
      case 'unlog':     return out_(unlog_(req.id));
      case 'history':   return out_(history_(req.from, req.to));
      case 'saveState': return out_(saveState_(req.state));
      case 'loadState': return out_(loadState_());
      case 'plans':     return out_(plans_(req.from, req.to));
      case 'plan':      return out_(createPlan_(req.plan || {}));
      case 'unplan':    return out_(deletePlan_(req.id));
      case 'calendars': return out_(calendars_());
      case 'agenda':    return out_(agenda_(String(req.from || ''), String(req.to || ''), req.ids));
      default:          return out_({ ok: false, error: 'Unknown action: ' + req.action });
    }
  } catch (err) {
    return out_({ ok: false, error: String(err && err.message || err) });
  } finally {
    try { lock.releaseLock(); } catch (e) {}
  }
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/* ---------- sheets ---------- */
function sheet_(name, head) {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.getRange(1, 1, 1, head.length).setValues([head]).setFontWeight('bold');
    sh.setFrozenRows(1);
    // keep dates and times as plain text so Sheets never shifts them by time zone
    sh.getRange(1, 1, sh.getMaxRows(), head.length).setNumberFormat('@');
  }
  return sh;
}

function rows_(sh, head) {
  const n = sh.getLastRow() - 1;
  if (n < 1) return [];
  return sh.getRange(2, 1, n, head.length).getValues().map((r, i) => {
    const o = { _row: i + 2 };
    head.forEach((h, j) => o[h] = r[j] instanceof Date ? Utilities.formatDate(r[j], TZ, h === 'time' || h === 'start' ? 'HH:mm' : 'yyyy-MM-dd') : String(r[j]));
    return o;
  });
}

/* ---------- log ---------- */
function logRows_(rows) {
  const sh = sheet_('Log', LOG_HEAD);
  const seen = new Set(rows_(sh, LOG_HEAD).map(r => r.id));
  const fresh = rows.filter(r => r && r.id && !seen.has(String(r.id)));
  if (fresh.length) {
    const stamp = Utilities.formatDate(new Date(), TZ, "yyyy-MM-dd'T'HH:mm:ss");
    const values = fresh.map(r => LOG_HEAD.map(h => h === 'logged_at' ? stamp : (r[h] == null ? '' : String(r[h]))));
    sh.getRange(sh.getLastRow() + 1, 1, values.length, LOG_HEAD.length).setNumberFormat('@').setValues(values);
    markPlansDone_([...new Set(fresh.map(r => String(r.date)))]);
  }
  return { ok: true, added: fresh.length, ids: rows.map(r => r && r.id).filter(Boolean) };
}

function updateRow_(id, fields) {
  const sh = sheet_('Log', LOG_HEAD);
  const row = rows_(sh, LOG_HEAD).find(r => r.id === String(id));
  // a row that is gone from the Sheet is not an error worth retrying forever
  if (!row) return { ok: true, updated: false };
  Object.keys(fields).forEach(k => {
    const c = LOG_HEAD.indexOf(k);
    if (c > 0 && k !== 'id' && k !== 'logged_at') sh.getRange(row._row, c + 1).setValue(String(fields[k]));
  });
  return { ok: true, updated: true };
}

function unlog_(id) {
  const sh = sheet_('Log', LOG_HEAD);
  const row = rows_(sh, LOG_HEAD).find(r => r.id === String(id));
  if (row) sh.deleteRow(row._row);
  return { ok: true, removed: !!row };
}

function history_(from, to) {
  const sh = sheet_('Log', LOG_HEAD);
  const list = rows_(sh, LOG_HEAD)
    .filter(r => (!from || r.date >= from) && (!to || r.date <= to))
    .map(r => { delete r._row; return r; });
  return { ok: true, rows: list };
}

/* ---------- app state backup (slots, levels, your own exercises) ---------- */
function saveState_(state) {
  const sh = sheet_('State', ['state', 'saved_at']);
  const json = JSON.stringify(state || {});
  if (json.length > 45000) return { ok: false, error: 'State too large' };
  sh.getRange(2, 1, 1, 2).setNumberFormat('@').setValues([[json, Utilities.formatDate(new Date(), TZ, "yyyy-MM-dd'T'HH:mm:ss")]]);
  return { ok: true };
}

function loadState_() {
  const sh = sheet_('State', ['state', 'saved_at']);
  if (sh.getLastRow() < 2) return { ok: true, state: null };
  const [json, at] = sh.getRange(2, 1, 1, 2).getValues()[0];
  let state = null;
  try { state = JSON.parse(json); } catch (e) {}
  return { ok: true, state, saved_at: String(at) };
}

/* ---------- plans + Google Calendar ---------- */
function calendar_() {
  const found = CalendarApp.getCalendarsByName(CAL_NAME);
  if (found.length) return found[0];
  const cal = CalendarApp.createCalendar(CAL_NAME, { color: CalendarApp.Color.RED });
  return cal;
}

function createPlan_(plan) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(plan.date || '')) return { ok: false, error: 'Bad date' };
  if (!/^\d{2}:\d{2}$/.test(plan.start || '')) return { ok: false, error: 'Bad start time' };
  const minutes = Math.max(5, Math.min(600, parseInt(plan.minutes, 10) || 45));
  const start = Utilities.parseDate(plan.date + ' ' + plan.start, TZ, 'yyyy-MM-dd HH:mm');
  const end = new Date(start.getTime() + minutes * 60000);
  const items = Array.isArray(plan.items) ? plan.items : [];
  const title = String(plan.title || 'Training');
  // the app re-sends a plan it already made when you tick it done: update it, never duplicate it
  const psh = sheet_('Plan', PLAN_HEAD);
  const had = plan.id ? rows_(psh, PLAN_HEAD).find(r => r.id === String(plan.id)) : null;
  if (had) {
    if (plan.status && plan.status !== had.status) {
      psh.getRange(had._row, PLAN_HEAD.indexOf('status') + 1).setValue(String(plan.status));
      if (plan.status === 'done') {
        try {
          const old = calendar_().getEventById(had.event_id);
          if (old && old.getTitle().indexOf('✓') !== 0) old.setTitle('✓ ' + old.getTitle());
        } catch (e) {}
      }
    }
    return { ok: true, id: had.id, event_id: had.event_id, updated: true };
  }
  const desc = items.map(x => '• ' + x).join('\n') + (plan.link ? '\n\nOpen in the app: ' + plan.link : '');
  const ev = calendar_().createEvent(title, start, end, { description: desc });
  ev.removeAllReminders();
  ev.addPopupReminder(REMINDER_MIN);
  const id = plan.id || Utilities.getUuid();
  const sh = sheet_('Plan', PLAN_HEAD);
  sh.getRange(sh.getLastRow() + 1, 1, 1, PLAN_HEAD.length).setNumberFormat('@').setValues([[
    id, plan.date, plan.start, String(minutes), title, String(plan.tab || ''), JSON.stringify(items), ev.getId(), String(plan.status || 'planned'),
    Utilities.formatDate(new Date(), TZ, "yyyy-MM-dd'T'HH:mm:ss")
  ]]);
  return { ok: true, id, event_id: ev.getId() };
}

function deletePlan_(id) {
  const sh = sheet_('Plan', PLAN_HEAD);
  const row = rows_(sh, PLAN_HEAD).find(r => r.id === String(id));
  if (!row) return { ok: true, removed: false };
  try { const ev = calendar_().getEventById(row.event_id); if (ev) ev.deleteEvent(); } catch (e) {}
  sh.deleteRow(row._row);
  return { ok: true, removed: true };
}

/** Plans, kept in step with the calendar: moving or deleting the event in Google Calendar wins. */
function plans_(from, to) {
  const sh = sheet_('Plan', PLAN_HEAD);
  const cal = calendar_();
  const list = [];
  rows_(sh, PLAN_HEAD).reverse().forEach(r => {          // reverse so deleting rows keeps indexes valid
    let ev = null;
    try { ev = cal.getEventById(r.event_id); } catch (e) {}
    if (!ev) { sh.deleteRow(r._row); return; }          // deleted in Google Calendar
    const s = ev.getStartTime(), e = ev.getEndTime();
    const date = Utilities.formatDate(s, TZ, 'yyyy-MM-dd'), start = Utilities.formatDate(s, TZ, 'HH:mm');
    const minutes = String(Math.round((e - s) / 60000));
    if (date !== r.date || start !== r.start || minutes !== r.minutes) {
      sh.getRange(r._row, 2, 1, 3).setValues([[date, start, minutes]]);   // moved in Google Calendar
    }
    let items = [];
    try { items = JSON.parse(r.items || '[]'); } catch (err) {}
    const p = { id: r.id, date, start, minutes: +minutes, title: ev.getTitle(), tab: r.tab, items, status: r.status };
    if ((!from || date >= from) && (!to || date <= to)) list.push(p);
  });
  list.sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start));
  return { ok: true, plans: list };
}

function markPlansDone_(dates) {
  if (!dates.length) return;
  const psh = sheet_('Plan', PLAN_HEAD);
  const plans = rows_(psh, PLAN_HEAD).filter(p => dates.indexOf(p.date) >= 0 && p.status !== 'done');
  if (!plans.length) return;
  const log = rows_(sheet_('Log', LOG_HEAD), LOG_HEAD);
  const cal = calendar_();
  plans.forEach(p => {
    const done = log.filter(r => r.date === p.date && r.result === 'done');
    if (!done.length) return;
    try {
      const ev = cal.getEventById(p.event_id);
      if (ev) {
        if (ev.getTitle().indexOf('✓') !== 0) ev.setTitle('✓ ' + ev.getTitle());
        const lines = done.map(r => '✓ ' + r.exercise + (r.dose ? ' · ' + r.dose : '') + (r.feel ? ' · ' + r.feel : ''));
        ev.setDescription((ev.getDescription() || '') + '\n\nDone:\n' + lines.join('\n'));
      }
    } catch (e) {}
    psh.getRange(p._row, PLAN_HEAD.indexOf('status') + 1).setValue('done');
  });
}

/** Run once from the editor to create the tabs and the calendar and grant permissions. */
function setup() {
  sheet_('Log', LOG_HEAD);
  sheet_('Plan', PLAN_HEAD);
  sheet_('State', ['state', 'saved_at']);
  calendar_();
  Logger.log('Ready: tabs Log, Plan, State and calendar "' + CAL_NAME + '".');
}

/* ---------- your other calendars, read-only ----------
   The app can show what else is on a day (a work shift, say). It only ever
   reads the calendars you tick in the app, and never writes to them. */

function calendars_() {
  const own = calendar_().getId();
  const list = CalendarApp.getAllCalendars()
    .filter(c => c.getId() !== own)
    .map(c => ({ id: c.getId(), name: c.getName(), color: c.getColor(), primary: c.isMyPrimaryCalendar() }));
  list.sort((a, b) => (b.primary ? 1 : 0) - (a.primary ? 1 : 0) || a.name.localeCompare(b.name));
  return { ok: true, calendars: list };
}

function agenda_(from, to, ids) {
  if (!Array.isArray(ids) || !ids.length) return { ok: true, events: [] };
  if (!/^\d{4}-\d{2}-\d{2}$/.test(from)) from = Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(to)) to = from;
  const a = Utilities.parseDate(from + ' 00:00', TZ, 'yyyy-MM-dd HH:mm');
  let b = Utilities.parseDate(to + ' 23:59', TZ, 'yyyy-MM-dd HH:mm');
  if (b.getTime() - a.getTime() > 100 * 864e5) b = new Date(a.getTime() + 100 * 864e5);   // about three months at most
  const own = calendar_().getId(), out = [];
  const day = d => Utilities.formatDate(d, TZ, 'yyyy-MM-dd'), hm = d => Utilities.formatDate(d, TZ, 'HH:mm');
  ids.slice(0, 12).forEach(id => {
    if (String(id) === own) return;                    // your training is already in the app
    let cal = null;
    try { cal = CalendarApp.getCalendarById(String(id)); } catch (e) {}
    if (!cal) return;
    cal.getEvents(a, b).forEach(ev => {
      if (out.length >= 400) return;
      try { if (ev.getMyStatus() === CalendarApp.GuestStatus.NO) return; } catch (e) {}   // skip what you declined
      if (ev.isAllDayEvent()) {
        // all-day dates carry no real time; step to midday so a time zone cannot move the day
        const s = new Date(ev.getAllDayStartDate().getTime() + 12 * 36e5);
        const e = new Date(ev.getAllDayEndDate().getTime() - 12 * 36e5);
        out.push({ cal: cal.getName(), title: ev.getTitle(), allDay: true, date: day(s), start: '', endDate: day(e), end: '' });
      } else {
        const s = ev.getStartTime(), e = ev.getEndTime();
        out.push({ cal: cal.getName(), title: ev.getTitle(), allDay: false, date: day(s), start: hm(s), endDate: day(e), end: hm(e) });
      }
    });
  });
  out.sort((x, y) => (x.date + x.start).localeCompare(y.date + y.start));
  return { ok: true, events: out };
}
