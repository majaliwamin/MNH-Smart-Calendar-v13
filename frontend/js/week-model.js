/*!
 * MNH academic week model — Malawi-local date and time is the single source of truth.
 * Teaching weeks remain Monday–Friday only, starting Monday 9 November 2026.
 * The displayed academic week follows the real current week and advances each Monday in Malawi.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.MNHWeek = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";
  const TIME_ZONE = "Africa/Blantyre";
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const FIRST_MONDAY = new Date(Date.UTC(2026, 10, 9));
  const DAY_MS = 24 * 60 * 60 * 1000;
  const WEEKDAYS = 5;
  const WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const zoneFormatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: TIME_ZONE, calendar: "gregory", numberingSystem: "latn",
    year: "numeric", month: "2-digit", day: "2-digit", weekday: "short",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"
  });
  function normalise(offset) {
    const value = Math.trunc(Number(offset));
    return Number.isFinite(value) ? value : 0;
  }
  function zonedParts(value) {
    const parts = Object.fromEntries(zoneFormatter.formatToParts(value || new Date()).map((item) => [item.type, item.value]));
    return {
      year: Number(parts.year), month: Number(parts.month) - 1, day: Number(parts.day),
      weekday: WEEKDAY_NAMES.indexOf(parts.weekday),
      hour: Number(parts.hour), minute: Number(parts.minute), second: Number(parts.second)
    };
  }
  function localNow() { return zonedParts(new Date()); }
  function makeZonedDate(year, month, day, hour, minute) {
    const desired = Date.UTC(year, month, day, hour || 0, minute || 0, 0);
    let instant = desired;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const actual = zonedParts(new Date(instant));
      const represented = Date.UTC(actual.year, actual.month, actual.day, actual.hour, actual.minute, actual.second);
      instant += desired - represented;
    }
    return new Date(instant);
  }
  function timeText(value) {
    const parts = zonedParts(value);
    return String(parts.hour).padStart(2, "0") + ":" + String(parts.minute).padStart(2, "0");
  }
  function monday(offset) {
    return new Date(Date.UTC(FIRST_MONDAY.getUTCFullYear(), FIRST_MONDAY.getUTCMonth(),
      FIRST_MONDAY.getUTCDate() + normalise(offset) * 7));
  }
  function dateList(offset, count) {
    const start = monday(offset), total = count || WEEKDAYS, out = [];
    for (let i = 0; i < total; i += 1) {
      out.push(new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate() + i)));
    }
    return out;
  }
  function dateLabels(offset, count) {
    return dateList(offset, count).map((d) => d.getUTCDate() + " " + MONTHS[d.getUTCMonth()]);
  }
  function startParts(offset) {
    const m = monday(offset);
    return [m.getUTCFullYear(), m.getUTCMonth(), m.getUTCDate()];
  }
  function label(offset) {
    const value = normalise(offset);
    return value === currentOffset() ? "This week" : "Week " + value;
  }
  function range(offset) {
    const days = dateList(offset), a = days[0], b = days[days.length - 1];
    if (a.getUTCFullYear() !== b.getUTCFullYear()) {
      return MONTHS[a.getUTCMonth()] + " " + a.getUTCDate() + ", " + a.getUTCFullYear() +
        " – " + MONTHS[b.getUTCMonth()] + " " + b.getUTCDate() + ", " + b.getUTCFullYear();
    }
    if (a.getUTCMonth() !== b.getUTCMonth()) {
      return MONTHS[a.getUTCMonth()] + " " + a.getUTCDate() + " – " +
        MONTHS[b.getUTCMonth()] + " " + b.getUTCDate() + ", " + b.getUTCFullYear();
    }
    return MONTHS[a.getUTCMonth()] + " " + a.getUTCDate() + "–" + b.getUTCDate() + ", " + b.getUTCFullYear();
  }
  function isoMonday(offset) {
    const m = monday(offset);
    return m.getUTCFullYear() + "-" + String(m.getUTCMonth() + 1).padStart(2, "0") +
      "-" + String(m.getUTCDate()).padStart(2, "0");
  }
  function currentOffset() {
    const now = localNow(), today = Date.UTC(now.year, now.month, now.day);
    const mondayOfToday = today - ((now.weekday + 6) % 7) * DAY_MS;
    const first = Date.UTC(FIRST_MONDAY.getUTCFullYear(), FIRST_MONDAY.getUTCMonth(), FIRST_MONDAY.getUTCDate());
    return Math.floor((mondayOfToday - first) / (DAY_MS * 7));
  }
  function currentDayIndex(offset) {
    if (normalise(offset) !== currentOffset()) return -1;
    const weekday = (localNow().weekday + 6) % 7;
    return weekday < WEEKDAYS ? weekday : -1;
  }
  return {
    TIME_ZONE, MONTHS, FIRST_MONDAY, WEEKDAYS, monday, dateList, dateLabels,
    startParts, label, range, isoMonday, localNow, makeZonedDate, timeText,
    currentOffset, currentDayIndex
  };
});
