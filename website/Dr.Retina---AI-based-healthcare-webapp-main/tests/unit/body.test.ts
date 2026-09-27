import { describe, expect, it } from "vitest";
import { readBoundedBody, BodyTooLarge } from "@/lib/api/body";
describe("bounded upload transport", () => {
  it("preserves exact bytes", async () => {
    const request = new Request("http://localhost", { method:"POST", body:"retinal-image" });
    expect(new TextDecoder().decode(await readBoundedBody(request,100))).toBe("retinal-image");
  });
  it("rejects a declared oversized request", async () => {
    const request = new Request("http://localhost", { method:"POST",body:"abc",headers:{"content-length":"1000"} });
    await expect(readBoundedBody(request,10)).rejects.toBeInstanceOf(BodyTooLarge);
  });
  it("rejects oversized chunked content without trusting a header", async () => {
    const request = new Request("http://localhost", { method:"POST",body:"abcdefghijk" });
    await expect(readBoundedBody(request,10)).rejects.toBeInstanceOf(BodyTooLarge);
  });
});
