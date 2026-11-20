/* Openway Assistant: dates in words with an injected today (port of dates.py). */
(function (g) {
  'use strict';
  const O = (g.Openway = g.Openway || {});
  const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
  const MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];
  const DEFAULT_DAYS = 30;
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const pad = n => String(n).padStart(2, '0');
  function mk(y, m, d) { return new Date(Date.UTC(y, m - 1, d)); }
  function parse(iso) { return mk(+iso.slice(0, 4), +iso.slice(5, 7), +iso.slice(8, 10)); }
  function iso(d) { return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()); }
  function add(d, n) { return new Date(d.getTime() + n * 86400000); }
  function weekday(d) { return (d.getUTCDay() + 6) % 7; } // Monday = 0
  function lastOfMonth(y, m) { return add(mk(y + (m === 12 ? 1 : 0), (m % 12) + 1, 1), -1); }
  function span(label, a, b) { return { label, start: iso(a), end: iso(b) }; }

  function parseWhen(text, today) {
    let t = ' ' + String(text).toLowerCase().replace(/’/g, "'").replace(/[^a-z0-9' ]+/g, ' ') + ' ';
    t = t.replace(/\s+/g, ' ');
    const d0 = parse(today), wd = weekday(d0), nextMonday = add(d0, 7 - wd);
    const has = p => t.includes(' ' + p + ' ');
    if (has('tonight')) return span('tonight', d0, d0);
    if (has('today')) return span('today', d0, d0);
    if (has('tomorrow')) return span('tomorrow', add(d0, 1), add(d0, 1));
    if (has('next weekend')) { const sat = add(nextMonday, 5); return span('next weekend', sat, add(sat, 1)); }
    if (has('this weekend') || has('the weekend') || has('weekend')) {
      if (wd <= 4) { const sat = add(d0, 5 - wd); return span('this weekend', sat, add(sat, 1)); }
      return span('this weekend', d0, add(d0, 6 - wd));
    }
    if (has('next week')) return span('next week', nextMonday, add(nextMonday, 6));
    if (has('this week')) return span('this week', d0, add(d0, 6 - wd));
    for (let i = 0; i < 7; i++) {
      if (has('next ' + WEEKDAYS[i])) { const day = add(nextMonday, i); return span('next ' + cap(WEEKDAYS[i]), day, day); }
    }
    for (let i = 0; i < 7; i++) {
      if (has(WEEKDAYS[i]) || has(WEEKDAYS[i] + 's')) {
        const day = add(d0, (((i - wd) % 7) + 7) % 7);
        return span(cap(WEEKDAYS[i]), day, day);
      }
    }
    if (has('next month')) {
      const y = d0.getUTCFullYear() + (d0.getUTCMonth() === 11 ? 1 : 0), m = (d0.getUTCMonth() + 1) % 12 + 1;
      return span('next month', mk(y, m, 1), lastOfMonth(y, m));
    }
    if (has('this month')) return span('this month', d0, lastOfMonth(d0.getUTCFullYear(), d0.getUTCMonth() + 1));
    if (has('this year')) return span('this year', d0, mk(d0.getUTCFullYear(), 12, 31));
    for (let i = 0; i < 12; i++) {
      const name = MONTHS[i];
      if ((name !== 'may' && (has(name) || has(name.slice(0, 3)))) || (name === 'may' && (has('in may') || has('this may') || has('next may')))) {
        const y = d0.getUTCFullYear() + (i + 1 < d0.getUTCMonth() + 1 ? 1 : 0);
        const first = mk(y, i + 1, 1);
        const start = (y === d0.getUTCFullYear() && i + 1 === d0.getUTCMonth() + 1) ? (first > d0 ? first : d0) : first;
        return span(cap(name), start, lastOfMonth(y, i + 1));
      }
    }
    return null;
  }
  const defaultRange = today => { const d0 = parse(today); return span('the next ' + DEFAULT_DAYS + ' days', d0, add(d0, DEFAULT_DAYS)); };
  const dayText = s => { const d = parse(s.slice(0, 10)); return cap(WEEKDAYS[weekday(d)]) + ' ' + d.getUTCDate() + ' ' + cap(MONTHS[d.getUTCMonth()]); };
  function timeText(s) {
    if (s.length < 16) return '';
    const h = parseInt(s.slice(11, 13), 10), m = s.slice(14, 16);
    if (h < 6) return '';
    return ((h % 12) || 12) + ':' + m + ' ' + (h < 12 ? 'am' : 'pm');
  }
  function whenText(s) { const t = timeText(s); return t ? dayText(s) + ', ' + t : dayText(s); }
  function rangeText(w) { return w.start === w.end ? dayText(w.start) : dayText(w.start) + ' to ' + dayText(w.end); }
  function plusDays(s, n) { return iso(add(parse(s), n)); }
  const D = { WEEKDAYS, MONTHS, parseWhen, defaultRange, dayText, timeText, whenText, rangeText, plusDays, cap };
  O.dates = D;
  if (typeof module !== 'undefined') module.exports = D;
})(typeof globalThis !== 'undefined' ? globalThis : this);
