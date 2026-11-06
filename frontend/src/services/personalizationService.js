import api from "./api.js";

export async function fetchRecommendations(params = {}) {
  const response = await api.get("/recommendations", { params });
  return response.data;
}

export async function fetchTodayDigest() {
  const response = await api.get("/digests/today");
  return response.data;
}

export async function generateDigest(regenerate = false) {
  const response = await api.post("/digests/generate", { regenerate });
  return response.data;
}

export async function fetchDigestHistory(params = {}) {
  const response = await api.get("/digests/history", { params });
  return response.data;
}

export async function fetchDigest(digestId) {
  const response = await api.get(`/digests/${encodeURIComponent(digestId)}`);
  return response.data;
}

export async function fetchDigestSettings() {
  const response = await api.get("/digests/settings");
  return response.data;
}

export async function updateDigestSettings(settings) {
  const response = await api.put("/digests/settings", settings);
  return response.data;
}
