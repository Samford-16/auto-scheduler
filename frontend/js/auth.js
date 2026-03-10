const API = "http://34.28.196.192:5000";

function getToken() {
  return localStorage.getItem("token");
}

function getCompany() {
  const c = localStorage.getItem("company");
  return c ? JSON.parse(c) : null;
}

function setAuth(token, company) {
  localStorage.setItem("token", token);
  localStorage.setItem("company", JSON.stringify(company));
}

function clearAuth() {
  localStorage.removeItem("token");
  localStorage.removeItem("company");
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${getToken()}`
  };
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "login.html";
    return false;
  }
  return true;
}

function logout() {
  fetch(`${API}/logout`, { method: "POST", headers: authHeaders() }).finally(() => {
    clearAuth();
    window.location.href = "login.html";
  });
}

// Inject nav company name if element exists
document.addEventListener("DOMContentLoaded", () => {
  const el = document.getElementById("nav-company");
  if (el) {
    const c = getCompany();
    if (c) el.textContent = c.name;
  }
});