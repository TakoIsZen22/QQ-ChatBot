'use strict';
(() => {
  const $=s=>document.querySelector(s),native=()=>window.pywebview?.api;
  let latest=null,watchdog=null;
  async function call(action='status',body){
    if(native())return native().account(action,body??null);
    const r=await fetch('/api/account/'+action,{method:action==='status'?'GET':'POST',headers:action==='status'?{}:{'Content-Type':'application/json','X-Harness-Local':'1'},body:action==='status'?undefined:JSON.stringify(body||{})});
    const value=await r.json();if(!r.ok)throw Error(value.error||'账号操作未完成');return value;
  }
  function error(e){return String(e?.message||e||'账号操作未完成')}
  function choices(prefix){return '<div class="account-options" id="'+prefix+'-options"><label><input id="'+prefix+'-remember" type="checkbox">记住密码</label><label><input id="'+prefix+'-auto" type="checkbox">自动登录</label></div>'}
  function bindChoices(prefix){
    const available=!!(native()&&latest?.remember?.supported),remember=$('#'+prefix+'-remember'),auto=$('#'+prefix+'-auto');
    $('#'+prefix+'-options').hidden=!available;
    remember.checked=available&&!!latest.remember.saved;auto.checked=available&&!!latest.remember.auto_login;
    remember.onchange=()=>{if(!remember.checked)auto.checked=false};auto.onchange=()=>{if(auto.checked)remember.checked=true};
  }
  function options(prefix){return native()?{remember_password:$('#'+prefix+'-remember').checked,auto_login:$('#'+prefix+'-auto').checked}:{}}
  function gate(){
    let box=$('#account-gate');if(box)return box;
    box=document.createElement('section');box.id='account-gate';box.className='account-gate';
    box.setAttribute('aria-label','本机账号登录');
    box.innerHTML='<div class="account-card"><div class="account-brand"><img alt="" src="'+(document.body.dataset.accountPage?'/assets/icons/xiaojing-user-icon.png':'assets/xiaojing-user-icon.png')+'"><span>QQ ChatBot</span></div><h1>欢迎回来</h1><p>登录本机账号，继续你们的对话。</p><form id="account-login"><div class="account-fields"><label>本机账号<input id="account-username" name="username" maxlength="64" autocomplete="username" required></label><label>密码<input id="account-password" name="password" type="password" maxlength="128" autocomplete="current-password" required></label></div><div id="account-message" class="account-error" role="alert" aria-live="polite"></div><button class="button primary account-submit" type="submit">登录</button></form><p class="account-note">这是本机程序账号。QQ 登录仍使用机器人账号扫码。<br>忘记密码：查看项目 docs/LOCAL_LOGIN.md 的离线恢复步骤。</p><div class="account-foot"><button id="account-pause" type="button">全部暂停</button><button id="account-exit" type="button">退出界面</button></div></div>';
    const message=box.querySelector('#account-message');
    message.insertAdjacentHTML('beforebegin',choices('login'));
    document.body.append(box);
    $('#account-pause').onclick=async()=>{try{if(native())await native().request('safety',{mode:'paused'});else{const r=await fetch('/api/safety',{method:'POST',headers:{'Content-Type':'application/json','X-Harness-Local':'1'},body:JSON.stringify({mode:'paused'})});if(!r.ok)throw Error('服务尚未连接')}$('#account-message').textContent='聊天已全部暂停。'}catch(e){$('#account-message').textContent=error(e)}};
    $('#account-exit').hidden=!native();$('#account-exit').onclick=()=>native()?.window_action('exit_ui');
    return box;
  }
  async function lock(){await call('lock');location.reload()}
  function panel(){
    const note=$('#program-account-status');if(!note)return;
    note.textContent=latest?.configured?'已启用 · '+latest.username+'。'+(latest.remember?.saved?'密码已由 Windows 加密保存；'+(latest.remember.auto_login?'下次启动自动登录。':'自动登录关闭。'):'未保存登录密码。')+' 手动锁定或收进托盘会关闭自动登录，后台聊天继续。':'尚未启用。设置后，打开程序需要登录本机账号。';
    $('#program-account-edit').textContent=latest?.configured?'修改账号 / 密码':'设置本机账号';
    $('#program-account-lock').hidden=!latest?.configured;
    const quick=$('#account-quick-lock');if(quick)quick.hidden=!latest?.configured;
    let forget=$('#program-account-forget');if(!forget){forget=document.createElement('button');forget.id='program-account-forget';forget.className='button secondary';forget.textContent='忘记已保存的密码';$('#program-account-lock').after(forget);forget.onclick=async()=>{try{latest=await call('forget');panel();window.DFY?.toast('已清除保存的密码和自动登录。')}catch(e){window.DFY?.toast(error(e),true)}}}
    forget.hidden=!latest?.remember?.saved;
  }
  function edit(){
    if(!native()){window.DFY?.toast('请在桌面程序中设置或修改本机账号。',true);return}
    let dialog=$('#account-edit-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='account-edit-dialog';dialog.className='account-dialog';document.body.append(dialog)}
    const changing=latest?.configured;
    dialog.innerHTML='<h2>'+ (changing?'修改本机账号':'设置本机账号')+'</h2><p>账号仅用于这份本机安装。密码至少 8 个字符，不会上传到模型或 QQ。</p><form id="account-edit-form"><div class="account-fields">'+(changing?'<label>当前密码<input id="account-current" type="password" autocomplete="current-password" maxlength="128" required></label>':'')+'<label>账号<input id="account-new-username" autocomplete="username" maxlength="64" required></label><label>新密码<input id="account-new-password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required></label><label>确认密码<input id="account-confirm" type="password" autocomplete="new-password" minlength="8" maxlength="128" required></label></div><div class="account-error" id="account-edit-message" role="alert"></div><div class="account-panel-actions"><button class="button primary" type="submit">保存账号</button><button id="account-cancel" class="button secondary" type="button">取消</button></div></form>';
    $('#account-new-username').value=latest?.username||'';
    $('#account-edit-message').insertAdjacentHTML('beforebegin',choices('edit'));bindChoices('edit');
    const clear=()=>{dialog.querySelectorAll('input[type=password]').forEach(x=>x.value='')};
    $('#account-cancel').onclick=()=>dialog.close();dialog.onclose=()=>{clear();dialog.replaceChildren()};
    $('#account-edit-form').onsubmit=async e=>{
      e.preventDefault();const button=dialog.querySelector('[type=submit]');if(button.disabled)return;
      const body={username:$('#account-new-username').value,password:$('#account-new-password').value,...options('edit')};
      if(body.password!==$('#account-confirm').value){$('#account-edit-message').textContent='两次密码不一致。';clear();return}
      if(changing)body.current_password=$('#account-current').value;
      clear();button.disabled=true;
      try{latest=await call(changing?'change':'setup',body);panel();dialog.close();window.DFY?.toast(latest.warning||'本机账号已保存。',!!latest.warning)}
      catch(e){$('#account-edit-message').textContent=error(e)}finally{button.disabled=false;body.password='';body.current_password=''}
    };
    dialog.showModal();
  }
  async function ensure(){
    document.body.classList.add('account-pending');const box=gate();
    try{latest=await call()}catch(e){$('#account-message').textContent=error(e)+'；修复后重新打开程序。';await new Promise(()=>{})}
    if(latest.appearance){const t=latest.appearance.theme;document.documentElement.dataset.theme=t==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):t;document.documentElement.style.setProperty('--ui-scale',latest.appearance.font_scale||1)}
    if(!latest.authenticated&&native()){
      try{latest=await call('resume')}catch(e){$('#account-message').textContent=error(e)}
    }
    if(!latest.authenticated){
      bindChoices('login');
      const username=$('#account-username'),password=$('#account-password');
      username.value=latest.remember?.username||'';
      const canUseSaved=()=>native()&&latest.remember?.saved&&username.value===latest.remember.username;
      const updatePassword=()=>{const saved=canUseSaved();password.required=!saved;password.placeholder=saved?'已记住密码，直接点击登录':'请输入密码'};
      username.addEventListener('input',updatePassword);updatePassword();
      await new Promise(resolve=>{$('#account-login').onsubmit=async e=>{
        e.preventDefault();const button=$('#account-login [type=submit]');if(button.disabled)return;
        const body={username:username.value,password:password.value,...options('login')};if(native())body.use_saved=!!(canUseSaved()&&!body.password);password.value='';button.disabled=true;
        try{latest=await call('login',body);if(latest.warning)window.DFY?.toast(latest.warning,true);resolve()}catch(e){$('#account-message').textContent=error(e)}finally{button.disabled=false;body.password=''}
      }});
    }
    if(document.body.dataset.accountPage){location.replace('/');return}
    box.hidden=true;document.body.classList.remove('account-pending');
    $('#program-account-edit')?.addEventListener('click',edit);
    $('#program-account-lock')?.addEventListener('click',()=>window.DFY.guard(lock));
    $('#account-quick-lock')?.addEventListener('click',()=>window.DFY.guard(lock));
    panel();
    if(!watchdog)watchdog=setInterval(async()=>{try{const value=await call();if(!value.authenticated){document.body.classList.add('account-pending');location.reload()}else{latest=value;panel()}}catch{document.body.classList.add('account-pending');location.reload()}},5000);
  }
  window.AccountUI={ensure,lock,call};
  if(document.body?.dataset.accountPage)ensure();
})();
