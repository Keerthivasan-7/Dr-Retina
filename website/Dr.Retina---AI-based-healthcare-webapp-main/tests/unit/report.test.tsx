import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ReportPanel } from "@/features/screenings/ReportPanel";
import { apiClient } from "@/lib/api/client";
vi.mock("@/lib/api/client", () => ({ apiClient:vi.fn() }));
const api = vi.mocked(apiClient);
const report = {
  screening:{ id:"case-1",patient_id:"p1",status:"SENT_TO_DOCTOR",assigned_doctor_id:"d1",assignment_status:"ASSIGNED" },
  patient:{ id:"p1",fullName:"Synthetic Patient",mrn:"DR-TEST",age:50,gender:"Female" },
  quality:{ score:0.9,accepted:true,reasons:[],model_version:"q1" },
  ai:{ severity:"Mild NPDR",confidence:0.8,probabilities:{"No DR":0.2,"Mild NPDR":0.8},
       model_version:"fixture-v1",created_at:"2026-09-24T10:00:00Z",findings:[] },
  review:null,events:[],
};
afterEach(() => { cleanup(); vi.clearAllMocks(); });
describe("clinical review UI", () => {
  it("sends a separate doctor decision without modifying AI fields", async () => {
    api.mockImplementation(async (url, options) => options?.method ? {ok:true} as never : report as never);
    render(<ReportPanel id="case-1" canReview />);
    await screen.findByText("Doctor’s final assessment");
    fireEvent.change(screen.getByLabelText("Final assessment"), {target:{value:"Independent clinical assessment"}});
    fireEvent.click(screen.getByRole("button",{name:"Save doctor decision"}));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/screenings/case-1/reviews",expect.objectContaining({
      method:"POST",body:{decision:"VERIFIED",finalAssessment:"Independent clinical assessment",comments:"",reason:null},
    })));
    expect(screen.getByText(/Mild NPDR.*confidence/)).toBeVisible();
  });
  it("requires a reason and comments for additional analysis", async () => {
    api.mockResolvedValue(report as never);
    render(<ReportPanel id="case-1" canReview />);
    await screen.findByText("Doctor’s final assessment");
    fireEvent.change(screen.getByLabelText("Doctor decision"),{target:{value:"ADDITIONAL_ANALYSIS_REQUIRED"}});
    expect(screen.getByLabelText("Reason")).toBeVisible();
    expect(screen.getByLabelText("Clinical comments")).toBeRequired();
    expect(screen.queryByLabelText("Final assessment")).not.toBeInTheDocument();
  });
  it("does not expose doctor controls to read-only users", async () => {
    api.mockResolvedValue(report as never);
    render(<ReportPanel id="case-1" />);
    await screen.findByText("Doctor’s final assessment");
    expect(screen.queryByRole("button",{name:"Save doctor decision"})).not.toBeInTheDocument();
  });
});
