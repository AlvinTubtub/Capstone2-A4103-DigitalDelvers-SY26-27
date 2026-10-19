// Nominal external dispatch times are documented in docs/production-automation.md §4.
// These checks are scheduled on weekdays even when the PSE is closed for a holiday.
// Philippine Time is UTC+8 and does not observe daylight saving time.
const PHT_OFFSET_MS = 8 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;
const MINUTE_MS = 60 * 1000;

const CHECK_MINUTES_BY_DAY: Readonly<Record<number, readonly number[]>> = {
  0: [],
  1: [17 * 60 + 30],
  2: [16 * 60, 17 * 60 + 30],
  3: [16 * 60, 17 * 60 + 30],
  4: [16 * 60, 17 * 60 + 30],
  5: [16 * 60, 17 * 60 + 30],
  6: [],
};

export function getNextScheduledCheck(now: Date): Date {
  if (Number.isNaN(now.getTime())) {
    throw new RangeError("A valid current time is required");
  }

  const phtNow = new Date(now.getTime() + PHT_OFFSET_MS);
  const phtMidnightAsUtc = Date.UTC(
    phtNow.getUTCFullYear(),
    phtNow.getUTCMonth(),
    phtNow.getUTCDate(),
  );

  for (let dayOffset = 0; dayOffset <= 7; dayOffset += 1) {
    const dayAsUtc = phtMidnightAsUtc + dayOffset * DAY_MS;
    const weekday = new Date(dayAsUtc).getUTCDay();
    for (const minuteOfDay of CHECK_MINUTES_BY_DAY[weekday]) {
      const check = new Date(dayAsUtc + minuteOfDay * MINUTE_MS - PHT_OFFSET_MS);
      if (check.getTime() > now.getTime()) return check;
    }
  }

  throw new Error("No future scheduled check found within a week");
}
