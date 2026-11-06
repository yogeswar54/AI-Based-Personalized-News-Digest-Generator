import api from "./api.js";

export const interestService = {
  getCategories: () => api.get("/interests/categories"),
  getUserInterests: () => api.get("/users/interests"),
  updateUserInterests: (payload) => api.put("/users/interests", payload),
};
