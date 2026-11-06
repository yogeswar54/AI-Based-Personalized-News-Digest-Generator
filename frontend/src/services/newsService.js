import api from "./api.js";

export async function fetchNews(params = {}) {
  const response = await api.get("/news", { params });
  return response.data;
}

export async function fetchNewsCategories() {
  const response = await api.get("/news/categories");
  return response.data;
}

export async function fetchNewsSources() {
  const response = await api.get("/news/sources");
  return response.data;
}

export async function fetchNewsArticle(articleId) {
  const response = await api.get(`/news/${encodeURIComponent(articleId)}`);
  return response.data;
}

export async function fetchArticleSummary(articleId) {
  const response = await api.get(`/news/${encodeURIComponent(articleId)}/summary`);
  return response.data;
}

export async function fetchNewsGroups(params = {}) {
  const response = await api.get("/news/groups", { params });
  return response.data;
}

export async function fetchNewsGroup(groupId) {
  const response = await api.get(`/news/groups/${encodeURIComponent(groupId)}`);
  return response.data;
}

export async function fetchRelatedArticles(articleId) {
  const response = await api.get(`/news/${encodeURIComponent(articleId)}/related`);
  return response.data;
}
