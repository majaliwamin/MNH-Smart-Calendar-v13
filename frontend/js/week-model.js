/*!
 * MNH academic week model — the single source of truth for week numbering and dates.
 *
 * "This week" is the teaching week that starts on Monday 9 November 2026.
 * Week numbers are relative to that teaching block, never the ISO calendar week:
 *
 *   offset 0  ->  "This week"  ·  Nov 9–13, 2026
 *   offset 1  ->  "Week 1"     ·  Nov 16–20, 2026
 *   offset 2  ->  "Week 2"     ·  Nov 23–27, 2026   …
 *
 * Teaching weeks are Monday–Friday only: Saturdays and Sundays are never generated.
 * The same file is loaded by the browser (window.MNHWeek) and by the Node checks
 * (module.exports), so the app and its tests can never drift apart.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.MNHWeek = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const FIRST_MONDAY = new Date(2026, 10, 9); // Monday 9 November 2026 — "This week"
  const DAY_MS = 24 * 60 * 60 * 1000;
  const WEEKDAYS = 5;

  function normalise(offset) {
    const value = Math.trunc(Number(offset));
    return Number.isFinite(value) ? value : 0;
  }

  /** Monday that begins the academic week `offset` weeks after "This week". */
  function monday(offset) {
    return new Date(FIRST_MONDAY.getFullYear(), FIRST_MONDAY.getMonth(), FIRST_MONDAY.getDate() + normalise(offset) * 7);
  }

  /** Monday–Friday dates for one academic week (5 entries by default). */
  function dateList(offset, count) {
    const start = monday(offset);
    const total = count || WEEKDAYS;
    const out = [];
    for (let i = 0; i < total; i += 1) out.push(new Date(start.getFullYear(), start.getMonth(), start.getDate() + i));
    return out;
  }

  /** Short labels such as ["9 Nov", "10 Nov", …] for one academic week. */
  function dateLabels(offset, count) {
    return dateList(offset, count).map((d) => d.getDate() + " " + MONTHS[d.getMonth()]);
  }

  /** [year, monthIndex, day] of the Monday — the shape the app stores in WEEK_START. */
  function startParts(offset) {
    const m = monday(offset);
    return [m.getFullYear(), m.getMonth(), m.getDate()];
  }

  /** "This week" for the default week, then "Week 1", "Week 2", … */
  function label(offset) {
    const value = normalise(offset);
    return value > 0 ? "Week " + value : "This week";
  }

  /** Human date range of one academic week: "Nov 9–13, 2026", "Nov 30 – Dec 4, 2026". */
  function range(offset) {
    const days = dateList(offset);
    const a = days[0];
    const b = days[days.length - 1];
    if (a.getFullYear() !== b.getFullYear()) {
      return (
        MONTHS[a.getMonth()] + " " + a.getDate() + ", " + a.getFullYear() +
        " – " +
        MONTHS[b.getMonth()] + " " + b.getDate() + ", " + b.getFullYear()
      );
    }
    if (a.getMonth() !== b.getMonth()) {
      return MONTHS[a.getMonth()] + " " + a.getDate() + " – " + MONTHS[b.getMonth()] + " " + b.getDate() + ", " + b.getFullYear();
    }
    return MONTHS[a.getMonth()] + " " + a.getDate() + "–" + b.getDate() + ", " + b.getFullYear();
  }

  /** "2026-11-16" — used in PDF file names. */
  function isoMonday(offset) {
    const m = monday(offset);
    return m.getFullYear() + "-" + String(m.getMonth() + 1).padStart(2, "0") + "-" + String(m.getDate()).padStart(2, "0");
  }

  /** Academic offset of the week that contains today (independent of what the user is viewing). */
  function currentOffset() {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const mondayOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - ((today.getDay() + 6) % 7));
    return Math.round((mondayOfToday.getTime() - FIRST_MONDAY.getTime()) / DAY_MS / 7);
  }

  return { MONTHS, FIRST_MONDAY, WEEKDAYS, monday, dateList, dateLabels, startParts, label, range, isoMonday, currentOffset };
});
