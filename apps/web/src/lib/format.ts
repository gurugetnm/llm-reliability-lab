const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 60 * 60 * 24 * 365],
  ["month", 60 * 60 * 24 * 30],
  ["week", 60 * 60 * 24 * 7],
  ["day", 60 * 60 * 24],
  ["hour", 60 * 60],
  ["minute", 60],
];

const relativeTimeFormat = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** Formats an ISO timestamp as a short relative string, e.g. "3 hours ago". */
export function formatDistanceToNow(isoDate: string): string {
  const seconds = (Date.parse(isoDate) - Date.now()) / 1000;

  for (const [unit, unitSeconds] of UNITS) {
    if (Math.abs(seconds) >= unitSeconds) {
      return relativeTimeFormat.format(Math.round(seconds / unitSeconds), unit);
    }
  }
  return relativeTimeFormat.format(Math.round(seconds), "second");
}
