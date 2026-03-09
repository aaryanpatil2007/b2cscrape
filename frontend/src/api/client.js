const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export function getCompanies(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") qs.set(k, v);
  });
  const query = qs.toString();
  return request(`/companies/${query ? `?${query}` : ""}`);
}

export function getFilters() {
  return request("/companies/filters");
}

export function updateCompany(id, data) {
  return request(`/companies/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function runScrape(data) {
  return request("/scrape/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getOutreachLogs(companyId) {
  return request(`/companies/${companyId}/outreach-logs`);
}

export function addOutreachLog(data) {
  return request("/companies/outreach-log", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function enrichCompanyEmail(companyId) {
  return request(`/companies/${companyId}/enrich`, { method: "POST" });
}

export function enrichAllEmails() {
  return request("/companies/enrich-all", { method: "POST" });
}

export function sendEmail(companyId, data) {
  return request(`/companies/${companyId}/send-email`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}
