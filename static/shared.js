// ═══════════════════════════════════════
//  shared.js — Common utilities for all pages
// ═══════════════════════════════════════

const API = '/api/v1';

// ─── Auth State ───
let _token = localStorage.getItem('ag_token');
let _email = localStorage.getItem('ag_email');

function getToken()  { return _token; }
function getEmail()  { return _email; }
function isLoggedIn(){ return !!_token; }

function saveAuth(token, email) {
  _token = token; _email = email;
  localStorage.setItem('ag_token', token);
  localStorage.setItem('ag_email', email);
}

function clearAuth() {
  _token = null; _email = null;
  localStorage.removeItem('ag_token');
  localStorage.removeItem('ag_email');
}

// ─── API Helper ───
async function api(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (_token) headers['Authorization'] = `Bearer ${_token}`;
  try {
    const r = await fetch(API + path, {
      method, headers,
      body: body ? JSON.stringify(body) : undefined
    });
    const data = await r.json();
    if (!r.ok) return { _err: data.detail || JSON.stringify(data), _status: r.status };
    return data;
  } catch(e) {
    return { _err: e.message };
  }
}

// ─── Toast ───
let _toastTimer;
function showToast(msg, isError = false) {
  let el = document.getElementById('_toast');
  if (!el) {
    el = document.createElement('div');
    el.id = '_toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = 'toast ' + (isError ? 'toast-error' : 'toast-success');
  el.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
}

// ─── Cart Badge ───
async function refreshCartBadge() {
  if (!_token) return;
  const cart = await api('GET', '/cart/');
  const badge = document.getElementById('cart-count');
  if (!badge) return;
  const count = (cart.items || []).reduce((s, i) => s + i.quantity, 0);
  badge.textContent = count;
  badge.style.display = count > 0 ? 'flex' : 'none';
}

// ─── Shared Auth Modal ───
let _authMode = 'login'; // 'login' | 'register'
let _onAuthSuccess = null;

function openAuthModal(onSuccess) {
  _onAuthSuccess = onSuccess || null;
  _authMode = 'login';
  _renderAuthModal();
  document.getElementById('_auth-overlay').classList.add('active');
  document.getElementById('_auth-modal').classList.remove('hidden');
  requestAnimationFrame(() =>
    document.getElementById('_auth-modal').classList.add('active')
  );
}

function closeAuthModal() {
  document.getElementById('_auth-overlay').classList.remove('active');
  document.getElementById('_auth-modal').classList.remove('active');
  setTimeout(() => document.getElementById('_auth-modal').classList.add('hidden'), 280);
}

function _renderAuthModal() {
  const login = _authMode === 'login';
  document.getElementById('_auth-heading').textContent = login ? 'Welcome back' : 'Create account';
  document.getElementById('_auth-sub').textContent = login ? 'Sign in to continue' : 'Join Anti-Gravity today';
  document.getElementById('_auth-submit').textContent = login ? 'Sign In' : 'Register';
  document.getElementById('_auth-switch-text').textContent = login ? "Don't have an account?" : 'Already have an account?';
  document.getElementById('_auth-switch-btn').textContent = login ? 'Register' : 'Sign In';
  document.getElementById('_auth-err').classList.add('hidden');
}

async function _submitAuth(e) {
  e.preventDefault();
  const email = document.getElementById('_auth-email').value.trim();
  const pass  = document.getElementById('_auth-pass').value;
  const errEl = document.getElementById('_auth-err');
  const btn   = document.getElementById('_auth-submit');
  btn.disabled = true; btn.textContent = '…';
  errEl.classList.add('hidden');
  try {
    if (_authMode === 'register') {
      const r = await api('POST', '/auth/register', { email, password: pass });
      if (r._err) throw new Error(r._err);
    }
    const r = await api('POST', '/auth/login', { email, password: pass });
    if (!r.access_token) throw new Error(r.detail || 'Login failed');
    saveAuth(r.access_token, email);
    syncNavAuth();
    closeAuthModal();
    await refreshCartBadge();
    if (_onAuthSuccess) _onAuthSuccess();
    showToast(`✓ Signed in as ${email.split('@')[0]}`);
  } catch(err) {
    errEl.textContent = err.message; errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = _authMode === 'login' ? 'Sign In' : 'Register';
  }
}

// ─── Nav Auth Sync ───
function syncNavAuth() {
  const signInBtn = document.getElementById('nav-signin');
  const userPill  = document.getElementById('nav-user');
  const avatar    = document.getElementById('nav-avatar');
  const name      = document.getElementById('nav-name');
  if (!signInBtn) return;
  if (_token && _email) {
    signInBtn.classList.add('hidden');
    userPill.classList.remove('hidden');
    avatar.textContent = _email[0].toUpperCase();
    name.textContent   = _email.split('@')[0];
  } else {
    signInBtn.classList.remove('hidden');
    userPill.classList.add('hidden');
  }
}

function signOut() {
  clearAuth();
  syncNavAuth();
  refreshCartBadge();
  showToast('Signed out');
}

// ─── Inject shared HTML (nav + auth modal) ───
function injectSharedUI(activePage) {
  // Nav
  const nav = document.getElementById('shared-nav');
  if (nav) {
    nav.innerHTML = `
      <div class="nav-inner">
        <a href="/" class="brand">
          <div class="brand-icon">⚡</div>
          <span>APEX<span class="brand-accent">·</span>COMMERCE</span>
        </a>
        <nav class="nav-center">
          <a href="/products" class="nav-pill ${activePage==='products'?'active':''}">Products</a>
          <a href="/orders"   class="nav-pill ${activePage==='orders'  ?'active':''}">My Orders</a>
          <a href="/tracking" class="nav-pill ${activePage==='tracking'?'active':''}">Order Tracking</a>
        </nav>
        <div class="nav-right">
          <button id="nav-cart-btn" class="cart-btn" onclick="toggleCart()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
            </svg>
            Cart <span id="cart-count" class="cart-count" style="display:none">0</span>
          </button>
          <button id="nav-signin" class="btn-primary" onclick="openAuthModal()">Sign In</button>
          <div id="nav-user" class="user-pill hidden">
            <div class="user-avatar" id="nav-avatar">A</div>
            <span id="nav-name"></span>
            <button class="signout-btn" onclick="signOut()">×</button>
          </div>
        </div>
      </div>`;
  }

  // Auth modal + overlay
  const modals = document.getElementById('shared-modals');
  if (modals) {
    modals.innerHTML = `
      <div id="_auth-overlay" class="overlay" onclick="closeAuthModal()"></div>
      <div id="_auth-modal" class="auth-modal hidden">
        <button class="modal-close" onclick="closeAuthModal()">×</button>
        <div class="modal-logo">⚡</div>
        <h3 id="_auth-heading">Welcome back</h3>
        <p id="_auth-sub" class="modal-sub">Sign in to continue</p>
        <form id="_auth-form" onsubmit="_submitAuth(event)">
          <div class="field">
            <label>Email</label>
            <input id="_auth-email" type="email" placeholder="you@example.com" required>
          </div>
          <div class="field">
            <label>Password</label>
            <input id="_auth-pass" type="password" placeholder="••••••••" required>
          </div>
          <div id="_auth-err" class="form-error hidden"></div>
          <button type="submit" id="_auth-submit" class="btn-primary btn-block">Sign In</button>
        </form>
        <div class="modal-switch">
          <span id="_auth-switch-text">Don't have an account?</span>
          <button class="link-btn" id="_auth-switch-btn"
            onclick="_authMode=_authMode==='login'?'register':'login';_renderAuthModal()">Register</button>
        </div>
      </div>`;
  }

  syncNavAuth();
  refreshCartBadge();

  // Navbar scroll effect
  window.addEventListener('scroll', () => {
    const nb = document.querySelector('.navbar');
    if (nb) nb.classList.toggle('scrolled', window.scrollY > 20);
  });
}
