const rawApiUrl = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const API_URL = rawApiUrl.replace(/\/+$/, "");
const TOKEN_KEY = "bank_complaints_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(path, { method = "GET", params = {}, body } = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) {
      query.append(key, value);
    }
  });
  const queryString = query.toString();
  const url = `${API_URL}${path}${queryString ? "?" + queryString : ""}`;

  const headers = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Cannot reach the backend server. Please verify it is running on port 8000.");
  }

  if (!response.ok) {
    let message = `Request failed (status ${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) {
        message = "Validation error: please check the submitted form values.";
      }
    } catch {
      // response had no json body
    }
    if (response.status === 401 && token && path !== "/auth/login") {
      onUnauthorized();
    }
    throw new Error(message);
  }
  return response.json();
}

// Auth endpoints
export const login = (email, password) =>
  request("/auth/login", { method: "POST", body: { email, password } });

export const signup = (email, password, fullName) =>
  request("/auth/signup", {
    method: "POST",
    body: { email, password, full_name: fullName || null },
  });

export const forgotPassword = (email) =>
  request("/auth/forgot-password", { method: "POST", body: { email } });

export const resetPassword = (token, new_password) =>
  request("/auth/reset-password", { method: "POST", body: { token, new_password } });

export const getMe = () => request("/auth/me");

// Complaints endpoints
export const getComplaints = (params) => request("/complaints", { params });
export const getProducts = () => request("/complaints/meta/products");
export const getComplaint = (id) => request(`/complaints/${id}`);
export const analyzeComplaint = (id, refresh = false) =>
  request(`/complaints/${id}/analysis`, { method: "POST", params: refresh ? { refresh: true } : {} });

export const getSimilarComplaints = (id) => request(`/complaints/${id}/similar`);
export const draftReply = (id, instructions = "") =>
  request(`/complaints/${id}/draft-reply`, { method: "POST", body: { custom_instructions: instructions } });
export const approveComplaintResponse = (id, response_text) =>
  request(`/complaints/${id}/approve`, { method: "POST", body: { response_text } });
export const dispatchComplaintResponse = (id) =>
  request(`/complaints/${id}/dispatch`, { method: "POST" });

// RAG Regulations & Trends
export const askRule = (question) =>
  request("/regulations/ask", { method: "POST", body: { question } });

export const getSpikes = (params) => request("/trends/spikes", { params });

// Admin endpoints
export const getUsers = () => request("/auth/users");
export const updateUserRole = (user_id, role) =>
  request("/auth/users/role", { method: "PUT", body: { user_id, role } });

export async function loginWithGoogle(credential) {
  return request("/auth/google", {
    method: "POST",
    body: { credential },
  });
}

export async function verifyEmail(token) {
  return request("/auth/verify-email", {
    method: "POST",
    body: { token },
  });
}

