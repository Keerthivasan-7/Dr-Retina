import { describe, expect, it } from "vitest";
import {
  DoctorReviewSchema,
  LoginSchema,
  PatientRegistrationSchema,
} from "@/lib/validation/schemas";

describe("schemas", () => {
  it("rejects empty patient names and out-of-range ages", () => {
    expect(
      PatientRegistrationSchema.safeParse({ fullName: "", age: 52, gender: "Female" }).success,
    ).toBe(false);
    expect(
      PatientRegistrationSchema.safeParse({ fullName: "Asha", age: 400, gender: "Female" })
        .success,
    ).toBe(false);
    expect(
      PatientRegistrationSchema.safeParse({ fullName: "Asha Rao", age: 52, gender: "Female" })
        .success,
    ).toBe(true);
  });

  it("does not require an untrusted organization selection to sign in", () => {
    expect(
      LoginSchema.safeParse({ email: "a@b.c", password: "x", role: "DOCTOR", orgId: "" }).success,
    ).toBe(true);
    expect(
      LoginSchema.safeParse({ email: "a@b.c", password: "x", role: "DOCTOR", orgId: "org-apex" })
        .success,
    ).toBe(true);
  });

  it("validates doctor review verdicts", () => {
    expect(
      DoctorReviewSchema.safeParse({ screeningId: "s1", verdict: "CONFIRMED" }).success,
    ).toBe(true);
    expect(
      DoctorReviewSchema.safeParse({ screeningId: "s1", verdict: "MAYBE" }).success,
    ).toBe(false);
  });
});
