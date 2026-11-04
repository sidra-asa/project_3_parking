'use strict';
const API = '/api/v1';
function csrfToken() { return document.querySelector('meta[name="csrf-token"]').content; }
async function requestJSON(path, {method='GET', body, headers={}}={}) {
  const options = {method, credentials:'same-origin', headers:{...headers}};
  if (body !== undefined) {
    options.headers['Content-Type']='application/json';
    options.body=JSON.stringify(body);
  }
  if (method !== 'GET' && method !== 'HEAD') options.headers['X-CSRFToken']=csrfToken();
  const response = await fetch(`${API}${path}`, options);
  if (response.status === 204) return null;
  const result = await response.json().catch(()=>({error:{message:'伺服器回應格式錯誤'}}));
  if (!response.ok) {
    if (response.status===401 && !location.pathname.startsWith('/login')) location.assign('/login');
    throw new Error(result.error?.message || `HTTP ${response.status}`);
  }
  return result;
}
function notify(message, isError=false) {
  const host = document.getElementById('alertHost');
  const toast = document.createElement('div');
  toast.className=`toast text-bg-${isError ? 'danger' : 'success'} show border-0`;
  toast.innerHTML='<div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="關閉"></button></div>';
  toast.querySelector('.toast-body').textContent=message;
  host.append(toast);
  toast.querySelector('button').addEventListener('click',()=>toast.remove());
  setTimeout(()=>toast.remove(),5500);
}
const logout = document.getElementById('logoutBtn');
if (logout) logout.addEventListener('click',async()=>{
  try { await requestJSON('/auth/logout',{method:'POST',body:{}}); location.assign('/login'); }
  catch(e) { notify(e.message,true); }
});
