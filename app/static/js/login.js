'use strict';
document.getElementById('loginForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const button=document.getElementById('submitLogin');
  const err=document.getElementById('loginError');
  err.textContent=''; button.disabled=true;
  try {
    await requestJSON('/auth/login',{method:'POST',body:{
      username:document.getElementById('username').value,
      password:document.getElementById('password').value
    }});
    location.assign('/dashboard');
  } catch(ex) { err.textContent=ex.message; button.disabled=false; }
});
