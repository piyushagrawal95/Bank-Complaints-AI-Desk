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

async function request(path, { method = "GET", params = {}, body, timeout } = {}) {
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

  // Smart timeout: Give AI & batch operations up to 55s; standard queries 22s
  const defaultTimeout =
    path.includes("/analysis") ||
    path.includes("/draft-reply") ||
    path.includes("/ask") ||
    path.includes("/batch-create") ||
    path.includes("/extract-file")
      ? 55000
      : 22000;

  const timeoutMs = timeout || defaultTimeout;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    const fetchOptions = { method, headers, signal: controller.signal };
    if (body !== undefined) {
      fetchOptions.body = JSON.stringify(body);
    }
    response = await fetch(url, fetchOptions);
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new Error(
        "Request timed out. The cloud server may be waking up from idle mode (cold start). Please click Retry."
      );
    }
    const isLocal = API_URL.includes("localhost") || API_URL.includes("127.0.0.1");
    if (isLocal) {
      throw new Error("Cannot reach local backend server. Please verify uvicorn is running on port 8000.");
    } else {
      throw new Error(
        "Cannot connect to the backend server. The cloud service may be waking up or temporarily unavailable. Please retry in a moment."
      );
    }
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let message = `Request failed (status ${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string" && data.detail.trim()) {
        message = data.detail;
      } else if (Array.isArray(data.detail) && data.detail.length > 0) {
        const errorMsgs = data.detail.map((err) => {
          let msg = err.msg || "Invalid value";
          msg = msg.replace(/^Value error,\s*/i, "").replace(/^Assertion error,\s*/i, "");
          const loc = Array.isArray(err.loc) ? err.loc : [];
          const field = loc.length > 0 ? loc[loc.length - 1] : "";
          if (field && field !== "body") {
            const fieldName = String(field)
              .replace(/_/g, " ")
              .replace(/\b\w/g, (c) => c.toUpperCase());
            if (msg.toLowerCase().includes(fieldName.toLowerCase())) {
              return msg;
            }
            return `${fieldName}: ${msg}`;
          }
          return msg;
        });
        message = errorMsgs.filter(Boolean).join(". ") || "Please verify the submitted form values.";
      } else if (typeof data.message === "string" && data.message.trim()) {
        message = data.message;
      } else if (typeof data.error === "string" && data.error.trim()) {
        message = data.error;
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
export const login = (email, password, turnstile_token = null, captcha_token = null, captcha_answer = null) =>
  request("/auth/login", {
    method: "POST",
    body: {
      email,
      password,
      turnstile_token: turnstile_token || null,
      captcha_token: captcha_token || null,
      captcha_answer: captcha_answer || null,
    },
  });

export const signup = (email, password, fullName, turnstile_token = null, captcha_token = null, captcha_answer = null) =>
  request("/auth/signup", {
    method: "POST",
    body: {
      email,
      password,
      full_name: fullName || null,
      turnstile_token: turnstile_token || null,
      captcha_token: captcha_token || null,
      captcha_answer: captcha_answer || null,
    },
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
export const requestComplaintApproval = (id, response_text) =>
  request(`/complaints/${id}/request-approval`, { method: "POST", body: { response_text } });
export const approveComplaintResponse = (id, response_text, consumer_email = null) =>
  request(`/complaints/${id}/approve`, {
    method: "POST",
    body: { response_text, consumer_email: consumer_email || null },
  });

export const rejectComplaintResponse = (id, reason) =>
  request(`/complaints/${id}/reject`, {
    method: "POST",
    body: { reason },
  });

export const getSupervisors = () =>
  request("/auth/supervisors");

export const assignAgentSupervisor = (agent_id, supervisor_id) =>
  request("/auth/users/supervisor", {
    method: "PUT",
    body: { agent_id, supervisor_id: supervisor_id || null },
  });
export const getPendingApprovals = () =>
  request("/complaints/pending-approvals");
export const updateComplaintEmail = (id, consumer_email) =>
  request(`/complaints/${id}/email`, { method: "PUT", body: { consumer_email } });
export const createComplaint = (data) =>
  request("/complaints/create", { method: "POST", body: data });

export const createComplaintsBatch = (complaints) =>
  request("/complaints/batch-create", { method: "POST", body: { complaints } });

export async function extractComplaintFile(file) {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);

  const headers = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 55000);

  let res;
  try {
    res = await fetch(`${API_URL}/complaints/extract-file`, {
      method: "POST",
      headers,
      body: formData,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new Error("Document parsing timed out. Cloud server may be waking up. Please retry.");
    }
    throw new Error("Failed to reach server for document extraction. Please retry.");
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    let msg = `Extraction failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

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

// Role Upgrade Request & Approval Endpoints
export const requestRoleUpgrade = (requested_role, reason) =>
  request("/auth/role-upgrade/request", {
    method: "POST",
    body: { requested_role, reason: reason || null },
  });

export const getMyRoleUpgradeStatus = () => request("/auth/role-upgrade/my-status");

export const getPendingRoleUpgrades = () => request("/auth/role-upgrade/pending");

export const approveRoleUpgrade = (requestId) =>
  request(`/auth/role-upgrade/${requestId}/approve`, { method: "POST" });

export const rejectRoleUpgrade = (requestId) =>
  request(`/auth/role-upgrade/${requestId}/reject`, { method: "POST" });

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
