'use strict';
(() => {
 const instances=[];
 const labels={password_authenticating:'正在验证 QQ 账号密码…',password_accepted:'账号密码已接受，等待 QQ 内核确认…',
   password_captcha:'需要滑块验证，请打开安全验证窗口。',password_device:'需要新设备验证，请按腾讯页面和手机提示操作。',
   password_failed:'QQ 登录失败，请核对机器人 QQ 密码，或切换扫码。',password_expired:'验证超时，请重新提交密码或切换扫码。',
   ready:'QQ 已登录。',not_running:'输入机器人 QQ 密码后登录，程序会启动独立 QQ。'};
 const native=()=>window.pywebview?.api;
 function mount(parent,qrElements){
   const root=document.createElement('div');root.className='qq-login-panel';
   root.innerHTML='<div class="qq-login-tabs" role="group" aria-label="QQ 登录方式"><button type="button" class="active" data-login-mode="qr" aria-pressed="true">扫码登录</button><button type="button" data-login-mode="password" aria-pressed="false">账号密码</button></div><form class="qq-password-form" hidden autocomplete="off"><p class="qq-login-note">登录机器人 QQ。这里填写 QQ 密码，本机程序账号与 QQ 账号分别管理。</p><label>机器人 QQ<input class="qq-login-uin" readonly aria-label="机器人 QQ"></label><label>QQ 密码<input class="qq-login-password" type="password" maxlength="256" autocomplete="off" placeholder="填写 QQ 密码；已记住时可留空"></label><div class="qq-login-checks"><label><input type="checkbox" class="qq-login-remember">记住 QQ 密码</label><label><input type="checkbox" class="qq-login-auto">启动程序时自动登录 QQ</label></div><div class="qq-login-actions"><button type="submit" class="button primary qq-login-submit">登录 QQ</button><button type="button" class="text-button qq-login-forget">忘记已保存的 QQ 密码</button></div><p class="qq-login-status" role="status"></p><div class="qq-login-actions"><button type="button" class="button secondary qq-login-verify" hidden>打开安全验证</button><button type="button" class="button secondary qq-login-complete" hidden>我已完成设备验证</button></div><p class="qq-login-note">密码仅在本机交给 QQ 官方内核；勾选保存后由 Windows 当前用户加密。腾讯可能要求滑块或手机确认。</p></form>';
   parent.prepend(root);
   const $=s=>root.querySelector(s),form=$('form'),note=$('.qq-login-status'),password=$('.qq-login-password'),remember=$('.qq-login-remember'),auto=$('.qq-login-auto');
   let mode='qr',busy=false;
   async function load(){
     if(!native())return;
     const [status,saved]=await Promise.all([native().onboarding('status'),native().onboarding('password_status')]);
     $('.qq-login-uin').value=status.accounts?.bot_id||window.DFY.state.cfg?.qq?.bot_id||'';
     remember.checked=!!saved.saved;auto.checked=!!saved.auto;auto.disabled=!remember.checked;
     password.placeholder=saved.saved?'已记住 QQ 密码，留空即可登录':'请输入机器人 QQ 的密码';
   }
   function update(phase){
     if(mode!=='password')return;
     if(labels[phase])note.textContent=labels[phase];
     $('.qq-login-verify').hidden=!['password_captcha','password_device'].includes(phase);
     $('.qq-login-complete').hidden=phase!=='password_device';
     $('.qq-login-submit').disabled=busy||['ready','password_authenticating','password_accepted'].includes(phase);
   }
   async function run(action,body){
     if(busy)return;busy=true;$('.qq-login-submit').disabled=true;
     let phase;
     try{const result=await native().onboarding(action,body||null);phase=result.phase;note.textContent=labels[result.phase]||result.message||'已提交，请等待 QQ 确认。';
       if(result.phase)update(result.phase);await window.DFY.poll(true);return result;
     }catch(error){note.textContent=error?.message||'QQ 登录操作未成功。请检查接入是否启动；旧进程需在下方手动停止 QQ 后重新启动。';}
     finally{busy=false;$('.qq-login-submit').disabled=false;if(phase)update(phase);}
   }
   root.querySelectorAll('[data-login-mode]').forEach(b=>b.onclick=()=>window.DFY.guard(async()=>{
     mode=b.dataset.loginMode;password.value='';
     root.querySelectorAll('[data-login-mode]').forEach(x=>{const active=x===b;x.classList.toggle('active',active);x.setAttribute('aria-pressed',String(active))});
     form.hidden=mode!=='password';qrElements.forEach(x=>{if(x)x.classList.toggle('qq-login-qr-hidden',mode==='password')});
     if(mode==='password'){await load();const qr=await native().qr();update(qr.phase);password.focus()}
     else{await native().onboarding('refresh_qr');await window.DFY.poll(true)}
   }));
   remember.onchange=()=>{auto.disabled=!remember.checked;if(!remember.checked)auto.checked=false};
   form.onsubmit=e=>{e.preventDefault();if(busy)return;const body={password:password.value,remember:remember.checked,auto:auto.checked};password.value='';run('password_login',body).finally(()=>{body.password=''})};
   $('.qq-login-verify').onclick=()=>run('password_verify');$('.qq-login-complete').onclick=()=>run('password_verify',{completed:true});
   $('.qq-login-forget').onclick=()=>run('password_forget').then(load);
   const dialog=parent.closest('dialog');dialog?.addEventListener('close',()=>{password.value=''});
   instances.push({update,load});return root;
 }
 function init(){
   mount(document.querySelector('#qr-dialog'),[document.querySelector('.qr-image-wrap'),document.querySelector('.qr-caption'),document.querySelector('#refresh-qr')]);
   // Put the switch below the dialog title, not above it.
   const panel=document.querySelector('#qr-dialog .qq-login-panel');document.querySelector('#qr-dialog header').after(panel);
   const setup=document.querySelector('.setup-login')?.parentElement;
   if(setup){const panel=mount(setup,[document.querySelector('.setup-login'),document.querySelector('#setup-refresh-qr')]);setup.querySelector('h3').after(panel);}
   native()?.onboarding('password_auto').then(r=>{if(r.message)window.DFY.toast(r.message)}).catch(()=>window.DFY.toast('QQ 自动登录未成功，请在 QQ 接入中手动登录。',true));
 }
 window.QQLoginUI={init,update:phase=>instances.forEach(x=>x.update(phase))};
})();
