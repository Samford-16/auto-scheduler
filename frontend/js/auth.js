const API = "http://34.28.196.192:5000";

const SESSION_DURATION = 8 * 60 * 60 * 1000; // 8 hours in ms

function getToken() { return localStorage.getItem("token"); }
function getCompany() { const c = localStorage.getItem("company"); return c ? JSON.parse(c) : null; }
function authHeaders() { return { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` }; }

// ─── Session Expiry ───────────────────────────────────
function setLoginTime() {
  localStorage.setItem("login_time", Date.now().toString());
}

function isSessionExpired() {
  const loginTime = localStorage.getItem("login_time");
  if (!loginTime) return true;
  return (Date.now() - parseInt(loginTime)) > SESSION_DURATION;
}

function checkSession() {
  if (!getToken()) return;
  if (isSessionExpired()) {
    localStorage.removeItem("token");
    localStorage.removeItem("company");
    localStorage.removeItem("login_time");
    window.location.href = "login.html?reason=expired";
  }
}

// Immediately block page render if session is expired
(function() {
    if (getToken() && isSessionExpired()) {
        localStorage.removeItem("token");
        localStorage.removeItem("company");
        localStorage.removeItem("login_time");
        window.location.href = "login.html?reason=expired";
    }
})();

checkSession();
setInterval(checkSession, 60 * 1000);

function logout() {
  fetch(`${API}/logout`, { method: "POST", headers: authHeaders() })
    .finally(() => {
      localStorage.removeItem("token");
      localStorage.removeItem("company");
      localStorage.removeItem("login_time");
      applyTheme();
      window.location.href = "index.html";
    });
}

// ─── Theme System ────────────────────────────────────
function applyTheme() {
  const theme = localStorage.getItem("theme") || "dark";
  const hue   = localStorage.getItem("hue")   || "160";
  document.body.className = document.body.className
    .replace(/theme-\S+/g, "").trim();
  document.body.classList.add(`theme-${theme}`);
  document.documentElement.style.setProperty("--hue", hue);
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