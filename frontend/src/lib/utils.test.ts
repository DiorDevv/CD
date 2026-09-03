import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cn, relativeTime } from "./utils";

describe("cn", () => {
  it("tailwind klasslarni birlashtiradi va konfliktni hal qiladi", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-sm", false && "hidden", "font-medium")).toBe(
      "text-sm font-medium",
    );
  });
});

describe("relativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-03T12:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("soniya / daqiqa / soat / kunlarni hisoblaydi", () => {
    expect(relativeTime("2026-09-03T11:59:30Z")).toBe("30s oldin");
    expect(relativeTime("2026-09-03T11:45:00Z")).toBe("15 daqiqa oldin");
    expect(relativeTime("2026-09-03T09:00:00Z")).toBe("3 soat oldin");
    expect(relativeTime("2026-09-01T12:00:00Z")).toBe("2 kun oldin");
  });
});
