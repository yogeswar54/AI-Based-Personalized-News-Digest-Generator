import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewsFeedPage from "./NewsFeedPage.jsx";
import { fetchNews, fetchNewsCategories, fetchNewsGroups } from "../services/newsService.js";

vi.mock("../services/newsService.js", () => ({
  fetchNews: vi.fn(),
  fetchNewsCategories: vi.fn(),
  fetchNewsGroups: vi.fn(),
}));

describe("news feed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchNews.mockResolvedValue({
      items: [{
        id: "article-1",
        title: "Local technology report",
        category: "Technology",
        description: "A preview of today's technology news.",
        source: { name: "Example News" },
        published_at: "2026-11-06T09:00:00Z",
        url: "https://example.test/story",
      }],
      total_pages: 1,
    });
    fetchNewsCategories.mockResolvedValue({ categories: ["Technology", "Sports"] });
    fetchNewsGroups.mockResolvedValue({ items: [] });
  });

  it("loads articles and sends selected category/search filters to the API", async () => {
    render(
      <MemoryRouter>
        <NewsFeedPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Local technology report")).toBeInTheDocument();
    expect(fetchNews).toHaveBeenCalledWith({
      category: undefined,
      keyword: undefined,
      page: 1,
      limit: 6,
    });

    fireEvent.click(screen.getByRole("button", { name: "Technology" }));
    await waitFor(() => expect(fetchNews).toHaveBeenLastCalledWith({
      category: "Technology",
      keyword: undefined,
      page: 1,
      limit: 6,
    }));

    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "market" },
    });
    await waitFor(() => expect(fetchNews).toHaveBeenLastCalledWith({
      category: "Technology",
      keyword: "market",
      page: 1,
      limit: 6,
    }));
  });

  it("renders API errors and empty results as distinct states", async () => {
    fetchNews.mockRejectedValueOnce({
      response: { data: { detail: "Backend temporarily unavailable" } },
    });
    render(
      <MemoryRouter>
        <NewsFeedPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Backend temporarily unavailable")).toBeInTheDocument();

    fetchNews.mockResolvedValueOnce({ items: [], total_pages: 1 });
    fetchNewsCategories.mockResolvedValue({ categories: [] });
    fetchNewsGroups.mockResolvedValue({ items: [] });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("No articles match the selected filters.")).toBeInTheDocument());
  });
});
