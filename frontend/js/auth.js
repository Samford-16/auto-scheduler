const API = "http://34.28.196.192:5000";

function getToken() { return localStorage.getItem("token"); }
function getCompany() { const c = localStorage.getItem("company"); return c ? JSON.parse(c) : null; }

function authHeaders() {
  return { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` };
}

function logout() {
  fetch(`${API}/logout`, { method: "POST", headers: authHeaders() })
    .finally(() => { localStorage.clear(); window.location.href = "index.html"; });
}

function initSidebar(activePage) {
  const company = getCompany();
  const name = company ? company.name : "—";
  const initial = name.charAt(0).toUpperCase();

  document.getElementById("sidebar-company-name").textContent = name;
  document.getElementById("sidebar-company-initial").textContent = initial;

  // Set active nav item
  const items = document.querySelectorAll(".nav-item[data-page]");
  items.forEach(item => {
    if (item.dataset.page === activePage) item.classList.add("active");
  });
}
