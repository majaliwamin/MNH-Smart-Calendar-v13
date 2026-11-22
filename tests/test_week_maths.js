#!/usr/bin/env node
"use strict";
/**
 * Academic week checks: numbering starts on Monday 7 September 2026, the current
 * teaching block starts on Monday 9 November 2026 (offset 9), and every week now
 * holds seven Monday–Sunday dates.
 *
 * Run from the project root:  node tests/test_week_maths.js
 */
const assert = require("assert");
const path = require("path");
const WK = require(path.join(__dirname, "..", "frontend", "js", "week-model.js"));

// Labels: numbering starts at week 1; the preceding week is orientation.
assert.strictEqual(WK.label(0), "Week 1");
assert.strictEqual(WK.label(1), "Week 2");
assert.strictEqual(WK.label(2), "Week 3");
assert.strictEqual(WK.label(3), "Week 4");
assert.strictEqual(WK.label(-1), "Orientation Week", "the preceding week is orientation");

// Date ranges: every week ends on its Sunday, including month boundaries.
assert.strictEqual(WK.range(0), "Sep 7–13, 2026");
assert.strictEqual(WK.range(1), "Sep 14–20, 2026");
assert.strictEqual(WK.range(2), "Sep 21–27, 2026");
assert.strictEqual(WK.range(3), "Sep 28 – Oct 4, 2026");
assert.strictEqual(WK.range(4), "Oct 5–11, 2026");
assert.strictEqual(WK.range(5), "Oct 12–18, 2026");
assert.strictEqual(WK.range(9), "Nov 9–15, 2026");
assert.strictEqual(WK.range(10), "Nov 16–22, 2026");

// All seven day columns are generated, never hardcoded.
assert.deepStrictEqual(WK.dateLabels(0), ["7 Sep", "8 Sep", "9 Sep", "10 Sep", "11 Sep", "12 Sep", "13 Sep"]);
assert.deepStrictEqual(WK.dateLabels(3), ["28 Sep", "29 Sep", "30 Sep", "1 Oct", "2 Oct", "3 Oct", "4 Oct"]);
assert.deepStrictEqual(WK.dateLabels(9), ["9 Nov", "10 Nov", "11 Nov", "12 Nov", "13 Nov", "14 Nov", "15 Nov"]);

// Stable identifiers used in PDF file names.
assert.strictEqual(WK.isoMonday(0), "2026-09-07");
assert.strictEqual(WK.isoMonday(9), "2026-11-09");
assert.strictEqual(WK.isoMonday(10), "2026-11-16");
assert.deepStrictEqual(WK.startParts(9), [2026, 10, 9]);

// Every academic week runs Monday through Sunday and advances on Monday.
for (let offset = -2; offset <= 14; offset += 1) {
  const list = WK.dateList(offset);
  assert.strictEqual(list.length, WK.WEEKDAYS, "each academic week must hold seven days");
  assert.deepStrictEqual([...new Set(list.map((date) => date.getDay()))].sort(), [0, 1, 2, 3, 4, 5, 6],
    "unexpected weekday coverage in week offset " + offset);
  assert.strictEqual(WK.monday(offset).getDay(), 1, "each academic week must start on a Monday");
  assert.strictEqual(WK.dateLabels(offset).length, 7);
}

// Navigating forward and back returns exactly to the same dates and label.
const seen = new Map();
for (let offset = 0; offset <= 14; offset += 1) {
  seen.set(WK.isoMonday(offset), WK.range(offset));
}
for (let offset = 14; offset >= 0; offset -= 1) {
  assert.strictEqual(seen.get(WK.isoMonday(offset)), WK.range(offset), "week " + offset + " must be stable in both directions");
}

console.log("Academic week checks passed: week 10 = Nov 9–15, 2026 · seven-day Monday–Sunday weeks · dynamic labels.");
