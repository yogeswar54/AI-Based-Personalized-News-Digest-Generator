import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DailyDigestPage from "./DailyDigestPage.jsx";
import { fetchTodayDigest, generateDigest } from "../services/personalizationService.js";

vi.mock("../services/personalizationService.js", () => ({
  fetchDigest: vi.fn(),
  fetchTodayDigest: vi.fn(),
  generateDigest: vi.fn(),
}));

describe("daily digest", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows today's digest and its story sections", async () => {
    fetchTodayDigest.mockResolvedValue({
      digest: {
        title: "Your Daily News Digest",
        digest_date: "2026-11-06",
        timezone: "Asia/Kolkata",
        introduction: "Today's technology headlines.",
        total_articles: 1,
        sections: [{
          category: "Technology",
          articles: [{
            article_id: "story-1",
            title: "A technology story",
            summary: "The story summary.",
            source: "Example News",
            url: "https://example.test/story",
          }],
        }],
      },
    });
    render(<MemoryRouter><DailyDigestPage /></MemoryRouter>);

    expect(await screen.findByText("A technology story")).toBeInTheDocument();
    expect(screen.getByText("Today's technology headlines.")).toBeInTheDocument();
    expect(screen.getByText("The story summary.")).toBeInTheDocument();
  });

  it("allows generation when today's digest does not exist", async () => {
    fetchTodayDigest.mockResolvedValue({ status: "not_generated", digest: null });
    generateDigest.mockResolvedValue({
      digest: {
        title: "Your Daily News Digest",
        digest_date: "2026-11-06",
        timezone: "UTC",
        introduction: "No stories yet.",
        total_articles: 0,
        sections: [],
      },
    });
    render(<MemoryRouter><DailyDigestPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Generate today's digest" }));

    expect(await screen.findByText("No stories yet.")).toBeInTheDocument();
    expect(generateDigest).toHaveBeenCalledWith(false);
  });
});
