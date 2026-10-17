// ═══════════════════════════════════════
//  shared.js — Common utilities for Apex Commerce
// ═══════════════════════════════════════

const API = (window.location.hostname.includes('github.io'))
  ? 'https://e-commerce-product-catalogue.onrender.com/api/v1'
  : '/api/v1';

const DEMO_PRODUCTS = [
  { id: 1, name: "Mechanical Gaming Keyboard RGB", slug: "mech-keyboard-rgb", category: "Peripherals", price: 89.99, stock: 45, rating: 4.8, description: "Hot-swappable mechanical switches, per-key RGB backlighting, aircraft-grade aluminum frame.", image_url: "https://images.unsplash.com/photo-1595225476474-87563907a212?w=500&auto=format&fit=crop" },
  { id: 2, name: "Ultra-Wide Gaming Monitor 34\"", slug: "ultrawide-monitor-34", category: "Displays", price: 449.99, stock: 18, rating: 4.9, description: "144Hz refresh rate, 1ms response time, HDR400 curved IPS panel with USB-C power delivery.", image_url: "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&auto=format&fit=crop" },
  { id: 3, name: "Wireless Noise-Cancelling Headphones", slug: "anc-wireless-headphones", category: "Audio", price: 199.99, stock: 32, rating: 4.7, description: "Active noise cancellation, 40-hour battery life, high-resolution audio codecs (LDAC, AAC).", image_url: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop" },
  { id: 4, name: "Ergonomic Vertical Mouse", slug: "ergo-vertical-mouse", category: "Peripherals", price: 49.99, stock: 60, rating: 4.6, description: "Reduces wrist strain, dual Bluetooth and 2.4GHz wireless connectivity, 4000 DPI sensor.", image_url: "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=500&auto=format&fit=crop" },
  { id: 5, name: "Thunderbolt 4 Docking Station 12-in-1", slug: "tb4-dock-12in1", category: "Accessories", price: 179.99, stock: 24, rating: 4.8, description: "Dual 4K display support, 96W laptop charging, Gigabit Ethernet, SD card slots, USB-A and USB-C.", image_url: "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=500&auto=format&fit=crop" },
  { id: 6, name: "4K Pro Streaming Webcam with Ring Light", slug: "4k-streaming-webcam", category: "Cameras", price: 119.99, stock: 40, rating: 4.5, description: "Sony STARVIS sensor, auto-focus, stereo noise-reducing microphones, magnetic privacy shutter.", image_url: "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&auto=format&fit=crop" }
];

// ─── Auth State ───
let _token = localStorage.getItem('ag_token');
let _email = localStorage.getItem('ag_email') || 'demo@apexcommerce.io';

function getToken()  { return _token; }
function getEmail()  { return _email; }
function isLoggedIn(){ return !!_token || true; }

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

// ─── API Helper with Automatic Fallback ───
async function api(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (_token) headers['Authorization'] = `Bearer ${_token}`;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const r = await fetch(API + path, {
      method, headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    });
    clearTimeout(timeout);
    const data = await r.json();
    if (!r.ok) return { _err: data.detail || JSON.stringify(data), _status: r.status };
    return data;
  } catch(e) {
    // Graceful client fallback for demo
    if (path.includes('/products')) {
      return DEMO_PRODUCTS;
    }
    if (path.includes('/cart')) {
      return JSON.parse(localStorage.getItem('apex_cart') || '{"items":[],"total":0}');
    }
    return { _err: e.message };
  }
}

// ─── Toast System ───
function showToast(msg, isErr = false) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.className = 'toast show' + (isErr ? ' error' : '');
  setTimeout(() => { toast.className = 'toast'; }, 3000);
}

// ─── Shared UI Helpers ───
function updateAuthUI() {
  const authLink = document.getElementById('auth-link');
  if (!authLink) return;
  authLink.textContent = 'Demo Account';
  authLink.href = '#';
}

function updateCartBadge() {
  const badge = document.getElementById('cart-badge');
  if (!badge) return;
  const cart = JSON.parse(localStorage.getItem('apex_cart') || '{"items":[]}');
  const count = cart.items ? cart.items.reduce((s, i) => s + (i.quantity || 1), 0) : 0;
  badge.textContent = count;
  badge.style.display = count > 0 ? 'inline-block' : 'none';
}

document.addEventListener('DOMContentLoaded', () => {
  updateAuthUI();
  updateCartBadge();
});
