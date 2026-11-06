import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../context/AuthContext.jsx";
import { interestService } from "../services/interestService.js";
import {
  fetchDigestHistory,
  fetchDigestSettings,
  fetchRecommendations,
  updateDigestSettings,
} from "../services/personalizationService.js";
import { fetchArticleSummary, fetchNewsArticle, fetchNewsGroup } from "../services/newsService.js";
import Dashboard from "./Dashboard.jsx";
import DigestHistoryPage from "./DigestHistoryPage.jsx";
import DigestSettingsPage from "./DigestSettingsPage.jsx";
import InterestSelection from "./InterestSelection.jsx";
import NewsArticlePage from "./NewsArticlePage.jsx";
import NewsGroupPage from "./NewsGroupPage.jsx";
import RecommendationsPage from "./RecommendationsPage.jsx";

vi.mock("../context/AuthContext.jsx", () => ({ useAuth: vi.fn() }));
vi.mock("../services/interestService.js", () => ({
  interestService: {
    getCategories: vi.fn(),
    getUserInterests: vi.fn(),
    updateUserInterests: vi.fn(),
  },
}));
vi.mock("../services/newsService.js", () => ({
  fetchArticleSummary: vi.fn(),
  fetchNewsArticle: vi.fn(),
  fetchNewsGroup: vi.fn(),
}));
vi.mock("../services/personalizationService.js", () => ({
  fetchDigestHistory: vi.fn(),
  fetchDigestSettings: vi.fn(),
  fetchRecommendations: vi.fn(),
  fetchTodayDigest: vi.fn(),
  updateDigestSettings: vi.fn(),
}));

const story = {
  id: "article-1",
  title: "Technology breakthrough",
  category: "Technology",
  description: "A useful report.",
  processed_description: "A processed report.",
  source: { name: "Example News" },
  published_at: "2026-11-06T09:00:00Z",
  url: "https://example.test/story",
};

function renderAt(element, path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/news/:articleId" element={element} />
        <Route path="/news/groups/:groupId" element={element} />
        <Route path="/" element={element} />
        <Route path="/dashboard" element={<p>Dashboard page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("personalized pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows recommendations and the relevant explanation", async () => {
    fetchRecommendations.mockResolvedValue({
      interests: ["Technology"],
      items: [{
        article: story,
        reasons: ["Matches your Technology interest"],
        event_group: null,
      }],
      total: 1,
      limit: 12,
    });
    renderAt(<RecommendationsPage />);

    expect(await screen.findByText("Technology breakthrough")).toBeInTheDocument();
    expect(screen.getByText("Matches your Technology interest")).toBeInTheDocument();
    expect(fetchRecommendations).toHaveBeenCalledWith({ page: 1, limit: 12 });
  });

  it("renders a dashboard welcome, interests, and digest status", async () => {
    useAuth.mockReturnValue({
      user: { full_name: "Reader", interests: ["Technology"] },
      logout: vi.fn(),
    });
    fetchRecommendations.mockResolvedValue({ items: [] });
    const { fetchTodayDigest } = await import("../services/personalizationService.js");
    fetchTodayDigest.mockResolvedValue({ status: "completed" });
    renderAt(<Dashboard />);

    expect(screen.getByText("Welcome, Reader")).toBeInTheDocument();
    expect(screen.getByText("Technology")).toBeInTheDocument();
    expect(await screen.findByText("Today's personalized digest is ready.")).toBeInTheDocument();
  });

  it("loads an article and changes the selected AI summary length", async () => {
    fetchNewsArticle.mockResolvedValue(story);
    fetchArticleSummary.mockResolvedValue({
      status: "completed",
      summary: {
        short_summary: "Short version.",
        medium_summary: "Medium version.",
        detailed_summary: "Detailed version.",
        key_points: ["The important point."],
        important_facts: { people: [], organizations: [], locations: [], dates: [], numbers: [] },
      },
    });
    renderAt(<NewsArticlePage />, "/news/article-1");

    expect(await screen.findByText("Short version.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Medium" }));
    expect(screen.getByText("Medium version.")).toBeInTheDocument();
    expect(screen.getByText("The important point.")).toBeInTheDocument();
  });

  it("shows publisher coverage in a related news group", async () => {
    fetchNewsGroup.mockResolvedValue({
      event_title: "A shared technology event",
      category: "Technology",
      article_count: 2,
      representative_article_id: "article-1",
      keywords: ["launch"],
      articles: [
        { ...story, id: "article-1" },
        { ...story, id: "article-2", title: "Second publisher report", source: { name: "Other News" } },
      ],
    });
    renderAt(<NewsGroupPage />, "/news/groups/group-1");

    expect(await screen.findByText("A shared technology event")).toBeInTheDocument();
    expect(screen.getByText("Second publisher report")).toBeInTheDocument();
  });

  it("saves selected interests and updates authenticated state", async () => {
    const setUser = vi.fn();
    useAuth.mockReturnValue({ setUser });
    interestService.getCategories.mockResolvedValue({ data: { categories: ["Technology", "Sports"] } });
    interestService.getUserInterests.mockResolvedValue({ data: { interests: ["Technology"] } });
    interestService.updateUserInterests.mockResolvedValue({ data: { interests: ["Technology", "Sports"] } });
    renderAt(<InterestSelection />);

    fireEvent.click(await screen.findByRole("button", { name: /sports/i }));
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
    expect(interestService.updateUserInterests).toHaveBeenCalledWith({
      interests: ["Technology", "Sports"],
    });
  });

  it("loads and saves digest settings without losing user interests", async () => {
    fetchDigestSettings.mockResolvedValue({
      settings: {
        digest_enabled: false,
        digest_frequency: "daily",
        digest_time: "08:00",
        timezone: "UTC",
        articles_per_digest: 10,
      },
      interests: ["Technology"],
    });
    updateDigestSettings.mockResolvedValue({
      settings: {
        digest_enabled: true,
        digest_frequency: "daily",
        digest_time: "08:00",
        timezone: "UTC",
        articles_per_digest: 10,
      },
    });
    renderAt(<DigestSettingsPage />);

    expect(await screen.findByText(/Technology/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /enable scheduled daily digests/i }));
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Digest preferences saved.");
    expect(updateDigestSettings).toHaveBeenCalledWith(expect.objectContaining({
      digest_enabled: true,
      articles_per_digest: 10,
    }));
  });

  it("shows owned digest history items", async () => {
    fetchDigestHistory.mockResolvedValue({
      items: [{
        id: "digest-1",
        digest_date: "2026-11-06",
        total_articles: 3,
        introduction: "A concise daily overview.",
      }],
    });
    renderAt(<DigestHistoryPage />);

    expect(await screen.findByText("2026-11-06 · 3 stories")).toBeInTheDocument();
    expect(screen.getByText("A concise daily overview.")).toBeInTheDocument();
  });
});
