import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const relativeFormat = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

/** "3 minutes ago", "yesterday", or a date for anything older than a week. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const date = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  const seconds = Math.round((date.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return "just now";
  if (abs < 3600) return relativeFormat.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return relativeFormat.format(Math.round(seconds / 3600), "hour");
  if (abs < 7 * 86400) return relativeFormat.format(Math.round(seconds / 86400), "day");
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatPrice(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amount);
}
