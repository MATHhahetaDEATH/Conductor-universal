import { invoke } from '@tauri-apps/api/core';
import './style.css';

const app = document.querySelector('#app');
app.innerHTML = `
  <form class="login" id="login-form">
    <h1>Conductor</h1>
    <label>Server IP or URL<input id="server" placeholder="192.168.1.10" required /></label>
    <label>Username<input id="username" value="root" autocomplete="username" required /></label>
    <label>Password<input id="password" type="password" autocomplete="current-password" required /></label>
    <button id="submit" type="submit">Login</button>
    <p id="message" role="alert"></p>
  </form>
`;

const form = document.querySelector('#login-form');
const message = document.querySelector('#message');
const submit = document.querySelector('#submit');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submit.disabled = true;
  message.textContent = 'Signing in...';
  try {
    const token = await invoke('login', {
      server: document.querySelector('#server').value,
      username: document.querySelector('#username').value,
      password: document.querySelector('#password').value,
    });
    const base = normalizeServer(document.querySelector('#server').value);
    window.location.href = `${base}/#conductor-token=${encodeURIComponent(token)}`;
  } catch (error) {
    message.textContent = String(error);
    submit.disabled = false;
  }
});

function normalizeServer(value) {
  let base = value.trim();
  if (!/^https?:\/\//i.test(base)) base = `http://${base}`;
  if (!/:[0-9]+(?:\/|$)/.test(base.replace(/^https?:\/\//i, ''))) base += ':8678';
  return base.replace(/\/+$/, '');
}
