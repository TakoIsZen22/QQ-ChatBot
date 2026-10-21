'use strict';
(() => {
 const $=s=>document.querySelector(s),D=()=>window.DFY,N=()=>window.pywebview?.api;
 let timer=null,last=null,busy=false,refreshing=null,scanning=false;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
 function model(){return Object.fromEntries(['provider','base_url','key_env','main','auxiliary'].map(k=>[k,$('#setup-'+k).value.trim()]))}
 function provider(){const mag=$('#setup-provider').value==='magpie';$('#setup-base_url').readOnly=mag;if(mag){$('#setup-base_url').value='http://127.0.0.1:3425/v1';$('#setup-key_env').value='MAGPIE_API_KEY'}else if($('#setup-base_url').value==='http://127.0.0.1:3425/v1'){$('#setup-base_url').value='';$('#setup-key_env').value='HARNESS_API_KEY'}}
 async function refresh(){if(refreshing)return refreshing;refreshing=readStatus();try{return await refreshing}finally{refreshing=null}}
 async function readStatus(){
   if(!$('#onboarding-dialog').open)return;
   last=await N().onboarding('status');D().updateQQSession(last.bridge?.session);const j=last.job;window.QQLoginUI?.update(last.bridge?.session?.phase);
   // 复用本机已装的 QQ 时不显示为「独立 QQ」，避免用户以为程序又装了一份。
   const qqLabel=last.qq_client?.reused?'QQ：已复用本机安装':'QQ：'+(last.components.qq?'已就绪':'待准备');
   $('#setup-download-state').textContent=j.message+'\n独立 QQ 加载器（实验）：'+(last.components.bridge?'已就绪':'待准备')+' · '+qqLabel;
   for(const id of ['setup-refresh-qr','setup-stop-qq'])$('#'+id).disabled=j.running||busy;$('#setup-download').disabled=j.running||busy;$('#setup-save').disabled=j.running||busy;$('#setup-start').disabled=j.running||busy||!last.bridge?.launch_available;
   $('#setup-detect-local').disabled=scanning;document.querySelectorAll('[data-use-local]').forEach(b=>b.disabled=j.running||busy);
   const progress=$('#setup-progress');progress.hidden=!j.running;if(j.total){progress.value=j.received/j.total;$('#setup-download-state').textContent+='\n'+Math.round(j.received/1024/1024)+' / '+Math.round(j.total/1024/1024)+' MB'}else progress.removeAttribute('value');
   const online=last.bridge?.session?.online&&D().state.status?.qq_online&&D().state.status?.qq_connected;$('#setup-finish').disabled=!online;
   if(online){$('#setup-login-state').textContent='✓ 机器人 QQ 已在线。确认两账号已是好友，点击“开始聊天，只回复”。';$('#setup-qr').hidden=true}
   else if(last.bridge?.session?.online){$('#setup-login-state').textContent='QQ 已登录，正在连接聊天消息通道，请稍候…';$('#setup-qr').hidden=true}
   else{const qr=await N().qr();$('#setup-qr').hidden=qr.state!=='ready';if(qr.state==='ready'){$('#setup-qr').src=qr.data_url;$('#setup-login-state').textContent='用机器人账号登录手机 QQ，扫描此码并确认登录。之后切回你的 QQ 给它发消息。'}else $('#setup-login-state').textContent=qr.message||last.bridge?.message||(qr.state==='expired'?'二维码已过期，请点击“刷新二维码”。':'等待二维码。先保存设置、准备组件，再点击“扫码接入”。若 QQ 退出，请查看使用教程的排错部分。')}
 }
 async function action(name,body){if(busy)return;busy=true;for(const id of ['setup-start','setup-refresh-qr','setup-stop-qq','setup-download','setup-save'])$('#'+id).disabled=true;document.querySelectorAll('[data-use-local]').forEach(b=>b.disabled=true);$('#setup-result').textContent='正在处理…';try{const r=await N().onboarding(name,body||null);$('#setup-result').textContent=r.message||'下载已在后台开始，可随时关闭向导后回来查看。';await D().poll(true)}catch(e){$('#setup-result').textContent=String(e?.message||e);throw e}finally{busy=false;await refresh()}}
 async function scanLocal(){
   if(scanning)return;scanning=true;$('#setup-detect-local').disabled=true;
   try{
   const box=$('#setup-local-results');box.textContent='正在检测安装位置、版本与关键程序文件…';
   const result=await N().onboarding('local_clients');box.replaceChildren();
   box.append(el('p','已适配：'+result.supported_versions.join('、')+'。未知版本需要适配，不能保证所有 QQ 版本通用。'));
   if(!result.clients.length)box.append(el('p','未在标准安装位置找到 QQ，可使用下方独立组件下载。'));
   for(const client of result.clients){
     const row=el('div');row.append(el('p',(client.version||'未知版本')+' · '+client.dir),el('p',client.reason));
     if(client.compatible){const button=el('button','复制此版本到独立目录','button secondary small');button.dataset.useLocal='1';button.disabled=busy||last?.job?.running;button.onclick=()=>D().guard(()=>action('use_local',{index:client.index}));row.append(button)}
     box.append(row);
   }
   box.append(el('p',result.message));
   }finally{scanning=false;$('#setup-detect-local').disabled=false}
 }
 async function open(){
   if(!N())throw Error('首次设置向导请在 Windows 桌面程序中使用');
   const data=await N().onboarding('status');last=data;
   for(const k of ['provider','base_url','key_env','main','auxiliary'])$('#setup-'+k).value=data.model[k]||'';
   $('#setup-base_url').readOnly=data.model.provider==='magpie';
   for(const k of ['owner_name','owner_id','bot_id'])$('#setup-'+k).value=data.accounts[k]||'';
   $('#onboarding-dialog').showModal();await refresh();if(timer)clearInterval(timer);timer=setInterval(()=>D().guard(refresh),1800);
 }
 function init(){
   const dialog=el('dialog');dialog.id='onboarding-dialog';dialog.setAttribute('aria-labelledby','setup-title');
   // Static UI only. Imported docs, API errors, account values and QR state use textContent/value.
   dialog.innerHTML='<header><div><div class="eyebrow">WELCOME TO QQ CHATBOT</div><h2 id="setup-title">从第一次见面开始</h2></div><div><button id="setup-pause" class="button subtle danger small">全部暂停</button><button id="setup-close" class="icon-button" aria-label="关闭向导">×</button></div></header><div class="setup-body"><div class="setup-steps"><span class="current">01 · 账号与模型</span><span>02 · 下载组件</span><span>03 · QQ 登录</span></div><p class="setup-note">需要两个不同的 QQ：你的 QQ 负责发消息，机器人 QQ 用来接收和回复消息。模型可用 Magpie 或自己的 OpenAI 兼容 API。QQ 登录由官方内核完成；登录后需在本次安装验证收发。</p><section class="setup-card"><h3>1. 设置你的搭档</h3><form id="setup-form"><div class="setup-grid"><label>怎样称呼你<input id="setup-owner_name" maxlength="40" autocomplete="off"></label><label>你的 QQ（主人号）<input id="setup-owner_id" inputmode="numeric" required autocomplete="off"></label><label>机器人 QQ（登录的号）<input id="setup-bot_id" inputmode="numeric" required autocomplete="off"></label><label>模型接入方式<select id="setup-provider"><option value="magpie">Magpie（已有用户可选）</option><option value="openai_compatible">自有 OpenAI 兼容 API</option></select></label><label class="setup-wide">API Base URL<input id="setup-base_url" placeholder="服务商提供的 Base URL，通常以 /v1 结尾" required></label><label>密钥环境变量名称（不是密钥）<input id="setup-key_env" placeholder="HARNESS_API_KEY" required></label><label>主模型 ID<input id="setup-main" list="setup-models" placeholder="填写服务中的真实模型 ID" required></label><label class="setup-wide">视觉辅助模型 ID（可选，识图时需要）<input id="setup-auxiliary" list="setup-models" placeholder="支持图片的模型 ID"></label></div><datalist id="setup-models"></datalist><p>密钥由你在 Windows 用户环境变量或 Magpie 中设置，请勿填进这里。修改环境变量后彻底退出程序再打开。只使用文字聊天时可先不填视觉模型。</p><div class="setup-actions"><button class="button primary" id="setup-save" type="submit">保存账号与模型</button><button class="button secondary" id="setup-check" type="button">检查 API / 读取模型</button><button class="text-button" type="button" data-guide="magpie">Magpie 教程</button><button class="text-button" type="button" data-guide="api">自有 API 教程</button></div></form><p id="setup-api-state" role="status"></p></section><section class="setup-card"><h3>2. 准备独立机器人 QQ</h3><p>先检测本机 QQ：已适配且文件校验通过的版本可复制程序文件到独立目录，重新扫码；不读取日常 QQ 登录态。未适配时可下载已兼容的独立 QQ，不影响日常 QQ。下载约 350 MB，请预留 3 GB 空间。</p><div class="setup-actions"><button class="button secondary" id="setup-detect-local">检测本机 QQ 兼容性</button><button class="button secondary" id="setup-download">下载并准备 QQ 组件</button></div><div id="setup-local-results" role="status"></div><p id="setup-download-state" role="status"></p><progress id="setup-progress" class="setup-progress" max="1" hidden></progress></section><section class="setup-card"><h3>3. 登录机器人 QQ</h3><div class="setup-actions"><button id="setup-start" class="button primary">扫码接入</button><button id="setup-refresh-qr" class="button secondary">刷新二维码</button><button id="setup-stop-qq" class="button secondary">停止 QQ 接入</button><button id="setup-refresh" class="button secondary">刷新状态</button></div><div class="setup-login"><img id="setup-qr" alt="本机机器人 QQ 登录二维码" hidden><p id="setup-login-state" role="status"></p></div><p>两个账号需要你手动加为好友。程序不会代你加好友或自动通过申请。首次启动保持暂停；确认在线后手动开启只回复。</p><button id="setup-finish" class="button primary" disabled>开始聊天，只回复</button></section><p id="setup-result" role="status"></p><div class="setup-actions"><button id="setup-tutorial" class="text-button">阅读完整新手教程 →</button><button id="setup-skip" class="text-button">稍后设置，先看看程序</button></div></div>';
   document.body.append(dialog);
   const about=document.querySelector('.program-about .program-toolbar');if(about){const b=el('button','首次使用 / QQ 接入','button primary small');b.id='program-onboarding';b.onclick=()=>D().guard(open);about.prepend(b);const help=el('button','新手教程','button secondary small');help.onclick=()=>D().guard(()=>window.GuideUI.open('start'));about.append(help)}
   $('#setup-provider').onchange=provider;
   $('#setup-detect-local').onclick=()=>D().guard(scanLocal);
   $('#setup-pause').onclick=()=>D().guard(async()=>{await D().api('safety',{mode:'paused'});await D().poll(true);D().toast('全部暂停已生效。')});
   $('#setup-form').onsubmit=e=>{e.preventDefault();D().guard(()=>action('save',{...Object.fromEntries(['owner_name','owner_id','bot_id'].map(k=>[k,$('#setup-'+k).value.trim()])),model:model()}))};
   $('#setup-refresh-qr').onclick=()=>D().guard(()=>action('refresh_qr'));$('#setup-stop-qq').onclick=()=>D().guard(()=>action('stop'));
   $('#setup-download').onclick=()=>D().guard(()=>action('install'));$('#setup-start').onclick=()=>D().guard(()=>action('start'));$('#setup-refresh').onclick=()=>D().guard(async()=>{await D().poll(true);await refresh()});
   $('#setup-finish').onclick=()=>D().guard(async()=>{await D().api('safety',{mode:'reply_only'});dialog.close();D().navigate('chat');await D().poll(true);D().toast('已开启只回复。用你的主人 QQ 给机器人发一条消息吧。')});
   $('#setup-check').onclick=()=>D().guard(async()=>{const m=model();$('#setup-api-state').textContent='正在读取模型清单，不发送聊天…';try{const r=await D().api('model-connection',{provider:m.provider,base_url:m.base_url,key_env:m.key_env});$('#setup-models').replaceChildren(...r.models.map(x=>{const o=el('option');o.value=x.id;return o}));$('#setup-api-state').textContent='连接成功，共 '+r.models.length+' 个模型。此检查不代表聊天、工具或视觉能力已验收。'}catch(e){$('#setup-api-state').textContent='检查未通过：'+String(e?.message||e)+'。不提供清单的服务可手填模型 ID。';throw e}});
   for(const id of ['setup-close','setup-skip'])$('#'+id).onclick=()=>dialog.close();dialog.onclose=()=>{clearInterval(timer);timer=null};
   dialog.querySelectorAll('[data-guide]').forEach(b=>b.onclick=()=>D().guard(()=>window.GuideUI.open(b.dataset.guide)));$('#setup-tutorial').onclick=()=>D().guard(()=>window.GuideUI.open('start'));
   if(N())N().onboarding('status').then(s=>{if(!s.configured)D().guard(open)}).catch(e=>D().toast(String(e),true));
 }
 window.OnboardingUI={init,open,refresh};
})();
