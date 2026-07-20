// ═══════════════════════════════════════════════════════
//  Ciclone External — Painel Admin JS
// ═══════════════════════════════════════════════════════

let ADMIN_TOKEN = "";
let ALL_USERS   = [];

// ── API base ──────────────────────────────────────────
// Troca pelo IP do seu servidor se rodar local
// No Netlify usa o proxy configurado no netlify.toml
const API = window.location.hostname === "localhost"
    ? "http://31.97.255.112:5555"
    : "http://31.97.255.112:5555";  // sempre bate direto na API

// ── helpers ───────────────────────────────────────────
function headers() {
    return {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + ADMIN_TOKEN
    };
}

async function api(method, path, body) {
    const opts = { method, headers: headers() };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(API + path, opts);
    const data = await r.json().catch(() => ({}));
    return { status: r.status, data };
}

function toast(msg, ok = true) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className   = ok ? "ok" : "err";
    t.style.display = "block";
    setTimeout(() => t.style.display = "none", 3000);
}

function fmtDate(str) {
    if (!str) return "—";
    return str.replace("T", " ").slice(0, 16);
}

// ── Login ─────────────────────────────────────────────
async function doLogin() {
    const token = document.getElementById("token-input").value.trim();
    if (!token) return;

    // Aceita o token localmente sem precisar da API
    ADMIN_TOKEN = token;
    localStorage.setItem("ciclone_token", token);
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("app").style.display = "block";
    loadDashboard();
}

function logout() {
    localStorage.removeItem("ciclone_token");
    ADMIN_TOKEN = "";
    document.getElementById("login-screen").style.display = "flex";
    document.getElementById("app").style.display = "none";
}

// Auto-login se tiver token salvo
window.onload = () => {
    const saved = localStorage.getItem("ciclone_token");
    if (saved) {
        document.getElementById("token-input").value = saved;
        doLogin();
    }
};

// ── Navegação ─────────────────────────────────────────
function showPage(name) {
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.getElementById("page-" + name).classList.add("active");
    event.target.classList.add("active");

    if (name === "dashboard") loadDashboard();
    if (name === "keys")      loadKeys();
    if (name === "usuarios")  loadUsers();
    if (name === "logs")      loadLogs();
}

// ── Dashboard ─────────────────────────────────────────
async function loadDashboard() {
    const [keysRes, usersRes, logsRes] = await Promise.all([
        api("GET", "/admin/keys"),
        api("GET", "/admin/users"),
        api("GET", "/admin/logs?limit=1"),
    ]);

    const keys  = Array.isArray(keysRes.data)  ? keysRes.data  : [];
    const users = Array.isArray(usersRes.data) ? usersRes.data : [];

    const used  = keys.filter(k => k.used).length;
    const free  = keys.filter(k => !k.used).length;
    const banned = users.filter(u => u.banned).length;

    document.getElementById("s-total-keys").textContent = keys.length;
    document.getElementById("s-used-keys").textContent  = used;
    document.getElementById("s-free-keys").textContent  = free;
    document.getElementById("s-users").textContent      = users.length;
    document.getElementById("s-banned").textContent     = banned;
    document.getElementById("s-logs").textContent       = "—";
}

// ── Gerar Keys ────────────────────────────────────────
let lastGeneratedKeys = [];

async function gerarKeys() {
    const plan = document.getElementById("gen-plan").value;
    const qty  = parseInt(document.getElementById("gen-qty").value) || 1;
    const note = document.getElementById("gen-note").value.trim() || plan;

    const { status, data } = await api("POST", "/admin/key/generate", { count: qty, note: plan + (note ? " | " + note : "") });

    if (status !== 200 || !data.keys) {
        toast("Erro ao gerar keys", false);
        return;
    }

    lastGeneratedKeys = data.keys;

    const box = document.getElementById("keys-output");
    box.style.display = "block";
    box.innerHTML = data.keys.map(k => `
        <div class="key-line">
            <span class="key-text">${k}</span>
            <button class="copy-btn" onclick="copyKey('${k}', this)">Copiar</button>
        </div>
    `).join("");

    document.getElementById("keys-actions").style.display = "flex";
    toast(`${data.keys.length} key(s) gerada(s) com sucesso!`);
}

function copyKey(key, btn) {
    navigator.clipboard.writeText(key);
    btn.textContent = "✓";
    setTimeout(() => btn.textContent = "Copiar", 1500);
}

function copiarTodas() {
    navigator.clipboard.writeText(lastGeneratedKeys.join("\n"));
    toast("Todas as keys copiadas!");
}

// ── Keys ──────────────────────────────────────────────
async function loadKeys() {
    const tbody = document.getElementById("keys-tbody");
    tbody.innerHTML = `<tr><td colspan="6" class="empty">Carregando...</td></tr>`;

    const { status, data } = await api("GET", "/admin/keys");
    if (status !== 200 || !Array.isArray(data)) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty">Erro ao carregar keys</td></tr>`;
        return;
    }

    const planFilter   = document.getElementById("filter-plan").value;
    const statusFilter = document.getElementById("filter-status").value;

    let keys = data;
    if (planFilter)              keys = keys.filter(k => k.plan === planFilter);
    if (statusFilter === "free") keys = keys.filter(k => !k.used);
    if (statusFilter === "used") keys = keys.filter(k => k.used);

    if (!keys.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty">Nenhuma key encontrada</td></tr>`;
        return;
    }

    tbody.innerHTML = keys.map(k => `
        <tr>
            <td><code style="color:#ffd200;font-size:12px">${k.key}</code></td>
            <td>${planBadge(k.plan)}</td>
            <td>${k.used
                ? '<span class="badge red">Usada</span>'
                : '<span class="badge green">Disponível</span>'
            }</td>
            <td>${k.used_by || "—"}</td>
            <td>${fmtDate(k.created_at)}</td>
            <td><button class="btn danger" style="padding:4px 12px;font-size:12px" onclick="revogarKey('${k.key}', this)">Revogar</button></td>
        </tr>
    `).join("");
}

function planBadge(plan) {
    const map = {
        "3DIAS":  '<span class="badge gray">3 Dias</span>',
        "SEMANA": '<span class="badge yellow">Semana</span>',
        "MENSAL": '<span class="badge green">Mensal</span>',
        "LIFE":   '<span class="badge" style="background:#1a0a2a;color:#cc88ff;border-color:#cc88ff30">Lifetime</span>',
    };
    return map[plan] || `<span class="badge gray">${plan||"—"}</span>`;
}

async function revogarKey(key, btn) {
    if (!confirm(`Revogar key ${key}?`)) return;
    btn.disabled = true;
    const { status, data } = await api("POST", "/admin/key/revoke", { key });
    if (status === 200) { toast("Key revogada!"); loadKeys(); }
    else { toast(data.error || "Erro ao revogar", false); btn.disabled = false; }
}

// ── Usuários ──────────────────────────────────────────
async function loadUsers() {
    const tbody = document.getElementById("users-tbody");
    tbody.innerHTML = `<tr><td colspan="7" class="empty">Carregando...</td></tr>`;

    const { status, data } = await api("GET", "/admin/users");
    if (status !== 200 || !Array.isArray(data)) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty">Erro ao carregar usuários</td></tr>`;
        return;
    }
    ALL_USERS = data;
    renderUsers(data);
}

function filterUsers() {
    const q = document.getElementById("search-user").value.toLowerCase();
    renderUsers(ALL_USERS.filter(u => u.username.toLowerCase().includes(q)));
}

function renderUsers(users) {
    const tbody = document.getElementById("users-tbody");
    if (!users.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty">Nenhum usuário encontrado</td></tr>`;
        return;
    }
    tbody.innerHTML = users.map(u => `
        <tr>
            <td><strong>${u.username}</strong></td>
            <td>${planBadge(u.plan)}</td>
            <td>${u.banned
                ? '<span class="badge red">Banido</span>'
                : '<span class="badge green">Ativo</span>'
            }</td>
            <td><code style="font-size:11px;color:#888">${u.hwid ? u.hwid.slice(0,12)+"..." : "—"}</code></td>
            <td><code style="font-size:11px;color:#666">${u.key_used || "—"}</code></td>
            <td>${fmtDate(u.created_at)}</td>
            <td style="display:flex;gap:6px">
                ${u.banned
                    ? `<button class="btn" style="padding:4px 12px;font-size:12px" onclick="unbanUser('${u.username}', this)">Desbanir</button>`
                    : `<button class="btn danger" style="padding:4px 12px;font-size:12px" onclick="banUser('${u.username}', this)">Banir</button>`
                }
            </td>
        </tr>
    `).join("");
}

async function banUser(username, btn) {
    if (!confirm(`Banir ${username}?`)) return;
    btn.disabled = true;
    const { status, data } = await api("POST", "/admin/user/ban", { username });
    if (status === 200) { toast(`${username} banido!`); loadUsers(); }
    else { toast(data.error || "Erro", false); btn.disabled = false; }
}

async function unbanUser(username, btn) {
    btn.disabled = true;
    const { status, data } = await api("POST", "/admin/user/unban", { username });
    if (status === 200) { toast(`${username} desbanido!`); loadUsers(); }
    else { toast(data.error || "Erro", false); btn.disabled = false; }
}

// ── Logs ──────────────────────────────────────────────
async function loadLogs() {
    const tbody = document.getElementById("logs-tbody");
    tbody.innerHTML = `<tr><td colspan="5" class="empty">Carregando...</td></tr>`;

    const limit = document.getElementById("log-limit").value || 50;
    const { status, data } = await api("GET", `/admin/logs?limit=${limit}`);

    if (status !== 200 || !Array.isArray(data)) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty">Erro ao carregar logs</td></tr>`;
        return;
    }
    if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty">Nenhum log encontrado</td></tr>`;
        return;
    }

    const actionColor = {
        login_ok:      "green",
        login_fail:    "red",
        register_ok:   "green",
        register_fail: "red",
        key_generated: "yellow",
        key_revoked:   "red",
        user_banned:   "red",
        user_unbanned: "green",
    };

    tbody.innerHTML = data.map(l => `
        <tr>
            <td style="font-size:12px;color:#666">${fmtDate(l.created_at)}</td>
            <td><span class="badge ${actionColor[l.action]||'gray'}">${l.action}</span></td>
            <td>${l.username || "—"}</td>
            <td style="font-size:12px;color:#555">${l.ip || "—"}</td>
            <td style="font-size:12px;color:#666">${l.detail || "—"}</td>
        </tr>
    `).join("");
}
