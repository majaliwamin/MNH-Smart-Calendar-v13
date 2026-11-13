#!/usr/bin/env node
"use strict";
/**
 * Academic week checks: "This week" is Monday 9 November 2026, weeks are numbered
 * from that teaching block, and every week holds five Monday–Friday dates.
 *
 * Run from the project root:  node tests/test_week_maths.js
 */
const assert = require("assert");
const path = require("path");
const WK = require(path.join(__dirname, "..", "frontend", "js", "week-model.js"));

const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// Labels: the default week is "This week", later weeks count up from 1.
assert.strictEqual(WK.label(0), "This week", "the default week must be labelled This week");
assert.strictEqual(WK.label(1), "Week 1");
assert.strictEqual(WK.label(2), "Week 2");
assert.strictEqual(WK.label(3), "Week 3");
assert.strictEqual(WK.label(-1), "This week", "navigation never runs before the teaching block starts");

// Date ranges: every week ends on its Friday, including the month boundary.
assert.strictEqual(WK.range(0), "Nov 9–13, 2026");
assert.strictEqual(WK.range(1), "Nov 16–20, 2026");
assert.strictEqual(WK.range(2), "Nov 23–27, 2026");
assert.strictEqual(WK.range(3), "Nov 30 – Dec 4, 2026");
assert.strictEqual(WK.range(4), "Dec 7–11, 2026");
assert.strictEqual(WK.range(5), "Dec 14–18, 2026");

// Day columns are generated, never hardcoded.
assert.deepStrictEqual(WK.dateLabels(0), ["9 Nov", "10 Nov", "11 Nov", "12 Nov", "13 Nov"]);
assert.deepStrictEqual(WK.dateLabels(1), ["16 Nov", "17 Nov", "18 Nov", "19 Nov", "20 Nov"]);
assert.deepStrictEqual(WK.dateLabels(3), ["30 Nov", "1 Dec", "2 Dec", "3 Dec", "4 Dec"]);

// Stable identifiers used in PDF file names.
assert.strictEqual(WK.isoMonday(0), "2026-11-09");
assert.strictEqual(WK.isoMonday(1), "2026-11-16");
assert.strictEqual(WK.isoMonday(5), "2026-12-14");
assert.deepStrictEqual(WK.startParts(2), [2026, 10, 23]);

// No weekend dates anywhere, and exactly five weekdays per academic week.
for (let offset = -2; offset <= 8; offset += 1) {
  const list = WK.dateList(offset);
  assert.strictEqual(list.length, WK.WEEKDAYS, "each academic week must hold five weekdays");
  list.forEach((date) => {
    const day = date.getDay();
    assert.ok(day >= 1 && day <= 5, "unexpected " + DAY_NAMES[day] + " in week offset " + offset);
  });
  assert.strictEqual(WK.monday(offset).getDay(), 1, "each academic week must start on a Monday");
  assert.ok(WK.dateLabels(offset).length === 5);
}

// Navigating forward and back returns exactly to the same dates and label.
const seen = new Map();
for (let offset = 0; offset <= 5; offset += 1) {
  seen.set(WK.isoMonday(offset), WK.range(offset));
}
for (let offset = 5; offset >= 0; offset -= 1) {
  assert.strictEqual(seen.get(WK.isoMonday(offset)), WK.range(offset), "week " + offset + " must be stable in both directions");
}

console.log("Academic week checks passed: This week = Nov 9–13, 2026 · six Monday–Friday weeks · dynamic labels.");
