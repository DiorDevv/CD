import { describe, expect, it } from "vitest";
import { AxiosError } from "axios";
import { apiError } from "./api";

describe("apiError", () => {
  it("string `detail` maydonini ajratadi", () => {
    const err = new AxiosError("fail");
    err.response = { data: { detail: "Login yoki parol noto'g'ri" } } as never;
    expect(apiError(err)).toBe("Login yoki parol noto'g'ri");
  });

  it("pydantic validatsiya massivini ajratadi", () => {
    const err = new AxiosError("fail");
    err.response = { data: { detail: [{ msg: "field required" }] } } as never;
    expect(apiError(err)).toBe("field required");
  });

  it("noma'lum xatoda fallback qaytaradi", () => {
    expect(apiError(new Error("boom"), "zaxira")).toBe("zaxira");
    expect(apiError(null)).toBe("Xatolik yuz berdi");
  });
});
