import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeverityBadge } from "@/components/ui/SeverityBadge";

describe("SeverityBadge", () => {
  it.each([
    ["Proliferative DR", "Proliferative DR (PDR)"],
    ["Severe NPDR", "Severe NPDR"],
    ["Moderate NPDR", "Moderate NPDR"],
    ["Mild NPDR", "Mild NPDR"],
    ["No DR", "No DR Detected"],
  ])("maps %s to a labeled badge", (input, label) => {
    render(<SeverityBadge severity={input} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("always renders textual priority, not color alone", () => {
    render(<SeverityBadge severity="Proliferative DR" />);
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
    expect(screen.getByText(/Immediate Action Required/)).toBeInTheDocument();
  });
});
