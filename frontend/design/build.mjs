/**
 * Build Wishly design-system preview cards for Claude Design (claude.ai/design).
 *
 * Each card is a self-contained HTML file: the app's real `src/index.css` is
 * inlined wholesale so previews always match the shipped stylesheet, and the
 * first line carries the `@dsCard` marker the Design System pane indexes.
 *
 * Usage:  node design/build.mjs        (from frontend/)
 * Output: design/dist/*.html
 *
 * Rendered email samples: drop backend-rendered emails (see
 * wishly.email.render) into design/email-samples/*.html and they are wrapped
 * into cards too.
 */

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const appCss = readFileSync(join(here, '../src/index.css'), 'utf8')
const outDir = join(here, 'dist')
mkdirSync(outDir, { recursive: true })

const FONTS = `
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&family=Spline+Sans+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
`

/** CSS that adapts app styles to a static preview stage. */
const STAGE_CSS = `
body { padding: 28px; }
.ds-stack { display: flex; flex-direction: column; gap: 1rem; align-items: flex-start; }
.ds-row { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
.ds-label {
  font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-faint);
  margin: 1.25rem 0 0.4rem;
}
.ds-label:first-child { margin-top: 0; }
/* Modals render in-flow on the stage instead of as a fixed overlay. */
.ds-static .modal-overlay { position: static; padding: 0; background: none; overflow: visible; }
.ds-static .modal-panel { border: 1px solid var(--line); }
`

function card({ file, title, group, body, extraCss = '', width = 720 }) {
  const html = `<!-- @dsCard group="${group}" width="${width}" -->
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${title}</title>
${FONTS}
<style>
${appCss}
${STAGE_CSS}
${extraCss}
</style>
</head>
<body>
${body}
</body>
</html>
`
  writeFileSync(join(outDir, file), html)
  console.log(`wrote ${file}`)
}

// ---------- Foundations ---------------------------------------------------- //

const SWATCHES = [
  ['--paper', 'Paper', 'page ground'],
  ['--card', 'Card', 'surfaces'],
  ['--ink', 'Ink', 'text'],
  ['--ink-soft', 'Ink soft', 'secondary text'],
  ['--ink-faint', 'Ink faint', 'hints, labels'],
  ['--line', 'Line', 'borders'],
  ['--pen', 'Pen', 'the red pen accent'],
  ['--pen-deep', 'Pen deep', 'hover, emphasis'],
  ['--pen-tint', 'Pen tint', 'accent wash'],
  ['--ok', 'OK', 'success'],
]

card({
  file: 'colors.html',
  title: 'Colors',
  group: 'Foundations',
  extraCss: `
.sw-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.75rem; }
.sw { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }
.sw-chip { height: 64px; border-bottom: 1px solid var(--line); }
.sw-meta { padding: 0.5rem 0.7rem; }
.sw-name { font-weight: 700; font-size: 0.85rem; }
.sw-var { font-family: var(--font-mono); font-size: 0.72rem; color: var(--ink-faint); }
.sw-use { font-size: 0.75rem; color: var(--ink-soft); }
`,
  body: `
<p class="ds-label">Paper &amp; pen — light and dark follow the OS setting</p>
<div class="sw-grid">
${SWATCHES.map(
  ([v, name, use]) => `  <div class="sw">
    <div class="sw-chip" style="background: var(${v})"></div>
    <div class="sw-meta">
      <div class="sw-name">${name}</div>
      <div class="sw-var">${v}</div>
      <div class="sw-use">${use}</div>
    </div>
  </div>`
).join('\n')}
</div>
`,
})

card({
  file: 'type.html',
  title: 'Type',
  group: 'Foundations',
  body: `
<div class="ds-stack">
  <span class="wordmark">wishly<span class="wordmark-dot">.</span></span>
  <p class="ds-label">Schibsted Grotesk — voice</p>
  <h1 style="font-size: 2.2rem; font-weight: 800; letter-spacing: -0.03em;">The dates you’d circle on the calendar</h1>
  <h2 style="font-size: 1.35rem;">Add an occasion</h2>
  <p style="color: var(--ink-soft); max-width: 34em;">
    Wishly keeps the birthdays and anniversaries you care about and emails you before
    each one — with enough lead time to actually do something about it.
  </p>
  <p class="ds-label">Spline Sans Mono — dates, countdowns, system labels</p>
  <div class="ds-row">
    <span class="row-count">In 19 days</span>
    <span class="mono" style="font-size: 0.85rem;">08:00 · America/Chicago</span>
    <span class="events-section-label" style="margin: 0;">Paused</span>
  </div>
</div>
`,
})

// ---------- Components ------------------------------------------------------ //

card({
  file: 'buttons.html',
  title: 'Buttons',
  group: 'Components',
  body: `
<div class="ds-stack">
  <p class="ds-label">Primary / secondary / ghost</p>
  <div class="ds-row">
    <button class="btn-primary">Add a date</button>
    <button class="btn-secondary">Try again</button>
    <button class="btn-ghost">How it works</button>
  </div>
  <p class="ds-label">Large (landing CTAs)</p>
  <div class="ds-row">
    <button class="btn-primary btn-large">Start tracking dates</button>
  </div>
  <p class="ds-label">Danger — outline until hover</p>
  <div class="ds-row">
    <button class="btn-danger">Remove all</button>
    <button class="btn-primary" disabled>Saving…</button>
    <button class="btn-secondary" disabled>Cancel</button>
  </div>
  <p class="ds-label">Quiet row actions</p>
  <div class="ds-row">
    <button class="btn-quiet">Edit</button>
    <button class="btn-quiet">Pause</button>
    <button class="btn-quiet btn-quiet-danger">Delete</button>
  </div>
</div>
`,
})

card({
  file: 'chips-pills.html',
  title: 'Chips & pills',
  group: 'Components',
  body: `
<div class="ds-stack">
  <p class="ds-label">Filter chips</p>
  <div class="filter-chips">
    <button class="chip chip-active">All</button>
    <button class="chip">Birthdays</button>
    <button class="chip">Anniversaries</button>
    <button class="chip">Custom</button>
  </div>
  <p class="ds-label">Countdown pills</p>
  <div class="ds-row">
    <span class="row-count row-count-soon">In 2 days</span>
    <span class="row-count">In 45 days</span>
    <span class="row-count row-count-paused">Paused</span>
  </div>
  <p class="ds-label">Send-log status</p>
  <div class="ds-row">
    <span class="history-status history-status-sent">Sent</span>
    <span class="history-status history-status-failed">Failed</span>
    <span class="history-status">Suppressed</span>
  </div>
  <p class="ds-label">Reminder lead times</p>
  <ul class="reminder-list">
    <li>30 days <button class="btn-icon" aria-label="Remove">×</button></li>
    <li>7 days <button class="btn-icon" aria-label="Remove">×</button></li>
    <li>Day of <button class="btn-icon" aria-label="Remove">×</button></li>
  </ul>
</div>
`,
})

card({
  file: 'event-row.html',
  title: 'Event row',
  group: 'Components',
  width: 760,
  body: `
<ul class="events-list">
  <li class="event-row">
    <div class="row-leaf" aria-hidden="true">
      <span class="leaf-month">Jul</span><span class="leaf-day">17</span>
    </div>
    <div class="row-main">
      <h3 class="row-title">Mom's birthday</h3>
      <p class="row-meta">Birthday · turns 64 · Reminds 30d · 7d · 1d · day of</p>
      <p class="row-note">She mentioned the blue ceramic vase at Harlow &amp; Co.</p>
    </div>
    <div class="row-side">
      <span class="row-count row-count-soon">In 6 days</span>
      <div class="row-actions">
        <button class="btn-quiet">Edit</button>
        <button class="btn-quiet">Pause</button>
        <button class="btn-quiet btn-quiet-danger">Delete</button>
      </div>
    </div>
  </li>
  <li class="event-row">
    <div class="row-leaf" aria-hidden="true">
      <span class="leaf-month">Oct</span><span class="leaf-day">7</span>
    </div>
    <div class="row-main">
      <h3 class="row-title">Passport renewal deadline</h3>
      <p class="row-meta">Custom · Reminds 60d · 30d · 7d</p>
    </div>
    <div class="row-side">
      <span class="row-count">In 88 days</span>
      <div class="row-actions">
        <button class="btn-quiet">Edit</button>
        <button class="btn-quiet">Pause</button>
        <button class="btn-quiet btn-quiet-danger">Delete</button>
      </div>
    </div>
  </li>
  <li class="event-row event-row-paused">
    <div class="row-leaf" aria-hidden="true">
      <span class="leaf-month">Oct</span><span class="leaf-day">31</span>
    </div>
    <div class="row-main">
      <h3 class="row-title">Jordan's birthday</h3>
      <p class="row-meta">Birthday · turns 30 · Reminds 7d · day of</p>
    </div>
    <div class="row-side">
      <span class="row-count row-count-paused">Paused</span>
      <div class="row-actions">
        <button class="btn-quiet">Edit</button>
        <button class="btn-quiet">Resume</button>
        <button class="btn-quiet btn-quiet-danger">Delete</button>
      </div>
    </div>
  </li>
</ul>
`,
})

card({
  file: 'forms.html',
  title: 'Forms',
  group: 'Components',
  width: 560,
  body: `
<form class="event-form" onsubmit="return false">
  <label>
    Title
    <input type="text" value="Mom's birthday" />
  </label>
  <fieldset class="type-picker">
    <legend>Type</legend>
    <div class="segmented">
      <button type="button" class="segment segment-active">Birthday</button>
      <button type="button" class="segment">Anniversary</button>
      <button type="button" class="segment">Custom</button>
    </div>
    <span class="field-hint">Chooses the email template for reminders.</span>
  </fieldset>
  <div class="date-row">
    <label>Month
      <select><option>July</option></select>
    </label>
    <label>Day
      <select><option>17</option></select>
    </label>
    <label>Year <span class="optional">(optional)</span>
      <input type="number" value="1962" />
    </label>
  </div>
  <label>
    Personal note <span class="optional">(optional)</span>
    <textarea rows="2">She mentioned the blue ceramic vase at Harlow &amp; Co.</textarea>
  </label>
  <label class="checkbox-row">
    <input type="checkbox" checked /> Send reminders for this event
  </label>
  <p class="form-error">Pick a day that exists in that month.</p>
  <p class="form-success">Preferences saved.</p>
  <div class="form-actions">
    <button type="button" class="btn-secondary">Cancel</button>
    <button type="submit" class="btn-primary">Save changes</button>
  </div>
</form>
`,
})

card({
  file: 'dialog.html',
  title: 'Confirm dialog',
  group: 'Components',
  width: 520,
  body: `
<div class="ds-static">
  <div class="modal-overlay">
    <div class="modal-panel modal-panel-sm">
      <h2 class="dialog-title">Delete “Mom's birthday”?</h2>
      <p class="dialog-body">
        The occasion and its reminder schedule will be removed. This cannot be undone.
      </p>
      <div class="form-actions">
        <button class="btn-secondary">Cancel</button>
        <button class="btn-danger">Delete occasion</button>
      </div>
    </div>
  </div>
</div>
`,
})

card({
  file: 'panels.html',
  title: 'Panels & empty state',
  group: 'Components',
  width: 640,
  body: `
<section class="panel">
  <h2>Profile</h2>
  <div class="profile-row">
    <span class="profile-initial">G</span>
    <div class="profile-details">
      <strong>Gavin</strong>
      <span class="text-muted">you@example.com</span>
      <span class="text-muted">Member since July 2026</span>
    </div>
  </div>
</section>
<section class="panel panel-danger">
  <h2>Danger zone</h2>
  <div class="danger-row">
    <div>
      <strong>Remove all occasions</strong>
      <p class="text-muted">Deletes all 6 occasions and their reminder schedules.</p>
    </div>
    <button class="btn-danger">Remove all</button>
  </div>
</section>
<div class="events-empty">
  <h2>Nothing circled yet</h2>
  <p>Add a birthday, an anniversary, or any date you can’t afford to forget.</p>
  <button class="btn-primary">Add your first date</button>
</div>
`,
})

card({
  file: 'calendar-leaf.html',
  title: 'Calendar leaf',
  group: 'Brand',
  width: 420,
  body: `
<div class="ds-row">
  <div class="row-leaf"><span class="leaf-month">Jul</span><span class="leaf-day">17</span></div>
  <div class="row-leaf"><span class="leaf-month">Oct</span><span class="leaf-day">7</span></div>
  <div class="row-leaf" style="transform: rotate(4deg); box-shadow: var(--shadow-pop);">
    <span class="leaf-month">Dec</span><span class="leaf-day">24</span>
  </div>
</div>
<p class="field-hint" style="margin-top: 1rem;">
  The tear-off calendar leaf — month in pen-red mono, day in display weight.
  Used in the events list and the landing hero.
</p>
`,
})

// ---------- Rendered email samples ------------------------------------------ //

const emailDir = join(here, 'email-samples')
let emails = []
try {
  emails = readdirSync(emailDir).filter((f) => f.endsWith('.html'))
} catch {
  // no samples directory — skip
}
for (const f of emails) {
  const html = readFileSync(join(emailDir, f), 'utf8')
  writeFileSync(join(outDir, f), `<!-- @dsCard group="Email" width="640" -->\n${html}`)
  console.log(`wrote ${f} (email sample)`)
}
