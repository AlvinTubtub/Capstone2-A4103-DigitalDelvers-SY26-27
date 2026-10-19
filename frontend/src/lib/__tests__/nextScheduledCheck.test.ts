import test from "node:test";
import assert from "node:assert/strict";
import { formatDateTimePht } from "@/lib/format";
import { getNextScheduledCheck } from "@/lib/nextScheduledCheck";

function next(iso: string): string {
  return getNextScheduledCheck(new Date(iso)).toISOString();
}

test("Monday has only the 5:30 PM Philippine Time check", () => {
  assert.equal(next("2026-10-19T08:00:00.000Z"), "2026-10-19T09:30:00.000Z");
  assert.equal(next("2026-10-19T09:29:59.999Z"), "2026-10-19T09:30:00.000Z");
});

test("Tuesday through Friday have 4:00 PM and 5:30 PM checks", () => {
  for (const day of [20, 21, 22, 23]) {
    const date = `2026-10-${day}`;
    assert.equal(next(`${date}T07:00:00.000Z`), `${date}T08:00:00.000Z`);
    assert.equal(next(`${date}T08:00:00.001Z`), `${date}T09:30:00.000Z`);
  }
});

test("a check at the exact current instant is no longer future", () => {
  assert.equal(next("2026-10-20T08:00:00.000Z"), "2026-10-20T09:30:00.000Z");
  assert.equal(next("2026-10-20T09:30:00.000Z"), "2026-10-21T08:00:00.000Z");
  assert.equal(next("2026-10-19T09:30:00.000Z"), "2026-10-20T08:00:00.000Z");
});

test("Friday evening and both weekend days roll over to Monday", () => {
  const monday = "2026-10-26T09:30:00.000Z";
  assert.equal(next("2026-10-23T09:30:00.000Z"), monday);
  assert.equal(next("2026-10-24T03:00:00.000Z"), monday);
  assert.equal(next("2026-10-25T15:59:00.000Z"), monday);
});

test("weekday checks still occur on a reviewed PSE holiday", () => {
  // Christmas Day is in backend/config/pse_holidays.py; external dispatch has no holiday guard.
  assert.equal(next("2026-12-25T07:00:00.000Z"), "2026-12-25T08:00:00.000Z");
  assert.equal(next("2026-12-25T08:00:00.000Z"), "2026-12-25T09:30:00.000Z");
});

test("scheduling and display do not depend on the device timezone", () => {
  const originalTimezone = process.env.TZ;
  try {
    for (const timezone of ["UTC", "America/New_York", "Asia/Tokyo"]) {
      process.env.TZ = timezone;
      const check = getNextScheduledCheck(new Date("2026-10-20T07:00:00.000Z"));
      assert.equal(check.toISOString(), "2026-10-20T08:00:00.000Z");
      assert.equal(formatDateTimePht(check.toISOString()), "Oct 20, 2026, 4:00 PM PHT");
    }
  } finally {
    if (originalTimezone === undefined) delete process.env.TZ;
    else process.env.TZ = originalTimezone;
  }
});
