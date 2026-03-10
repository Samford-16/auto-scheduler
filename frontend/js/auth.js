const API = "http://34.28.196.192:5000";

function getToken() { return localStorage.getItem("token"); }
function getCompany() { const c = localStorage.getItem("company"); return c ? JSON.parse(c) : null; }
function authHeaders() { return { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` }; }

function logout() {
  fetch(`${API}/logout`, { method: "POST", headers: authHeaders() })
    .finally(() => { localStorage.clear(); applyTheme(); window.location.href = "index.html"; });
}

// ─── Theme System ────────────────────────────────────
function applyTheme() {
  const theme  = localStorage.getItem("theme")  || "dark";
  const accent = localStorage.getItem("accent") || "emerald";
  document.body.className = document.body.className
    .replace(/theme-\S+/g, "").replace(/accent-\S+/g, "").trim();
  document.body.classList.add(`theme-${theme}`, `accent-${accent}`);
}

// Call immediately on every page load
applyTheme();

// ─── Sidebar ─────────────────────────────────────────
function initSidebar(activePage) {
  const company = getCompany();
  const name = company ? company.name : "—";
  const initial = name.charAt(0).toUpperCase();
  const nameEl = document.getElementById("sidebar-company-name");
  const initEl = document.getElementById("sidebar-company-initial");
  if (nameEl) nameEl.textContent = name;
  if (initEl) initEl.textContent = initial;
  const items = document.querySelectorAll(".nav-item[data-page]");
  items.forEach(item => {
    if (item.dataset.page === activePage) item.classList.add("active");
  });
}