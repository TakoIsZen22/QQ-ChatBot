'use strict';
(() => {
  const $=s=>document.querySelector(s);
  const native=()=>window.pywebview?.api;
  const toast=(...args)=>window.DFY.toast(...args);
  const guard=fn=>window.DFY.guard(fn);
  let dirty=false,busy=false,latest=null,pending=null;
  const switches=['start_with_windows','startup_hidden','auto_start_services','close_to_tray','minimize_to_tray','auto_recover'];
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  function appearance(settings) {
    const theme=settings.theme || 'system';
    document.documentElement.dataset.theme=theme==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):theme;
    document.documentElement.style.setProperty('--ui-scale',settings.font_scale || 1);
  }
  async function refresh() {
    if(native())latest=await native().preferences();
    else latest={settings:window.DFY.state.cfg?.desktop || {},startup:{supported:false,registered:false},version:window.DFY.state.status?.version||'—'};
    if(!dirty){for(const k of switches)$('#program-'+k).checked=!!latest.settings[k];$('#program-theme').value=latest.settings.theme || 'system';$('#program-font_scale').value=latest.settings.font_scale || 1;appearance(latest.settings)}
    $('#startup-registration').textContent=!latest.startup.supported?'请在桌面端查看自启状态':latest.startup.registered?'已登记 · 下次Windows登录生效':'尚未登记开机自启';
    $('#program-native-note').hidden=!!native();
    $('#program-save').disabled=!native();
    $('#program-version').textContent=latest.version;
    $('.sidebar-version span').textContent='本机控制台 · v'+latest.version;
    const recovery=latest.recovery;
    $('#program-tray-state').textContent=(latest.tray_available?'托盘可用 · 右键图标管理后台':'托盘状态将在正式桌面启动后显示')+(recovery?.limited?' · 恢复次数达到上限，请排障后手动启动':recovery&&!recovery.desired?' · 已手动停止，不自动拉起':'');
    if(native())await refreshBackups();
  }
  async function save(event) {
    event.preventDefault();if(!native())return;
    const patch=Object.fromEntries(switches.map(k=>[k,$('#program-'+k).checked]));
    patch.theme=$('#program-theme').value;patch.font_scale=Number($('#program-font_scale').value);
    $('#program-save').disabled=true;
    try{latest=await native().preferences(patch);dirty=false;appearance(latest.settings);await refresh();toast('程序设置已保存。窗口、主题和恢复设置立即生效。')}
    finally{$('#program-save').disabled=false}
  }
  async function refreshBackups() {
    if(!native())return;
    const rows=await native().maintenance('list');const list=$('#program-backups');list.replaceChildren();
    if(!rows.length){list.append(el('p','还没有快照。创建备份会一起保存JSONL、媒体附件和配置。','program-muted'));return}
    for(const row of rows){const item=el('div',undefined,'backup-item');const text=el('div');text.append(el('strong',row.name),el('small',row.invalid?'清单无效，请检查备份':`${row.files} 个数据文件 · ${row.records} 条记录`));
      const actions=el('div');const verify=el('button','校验','button secondary small');verify.type='button';verify.disabled=busy || !!row.invalid;verify.onclick=()=>guard(async()=>{const r=await native().maintenance('verify',row.name);toast(`校验通过：${r.files} 个文件，${r.records} 条记录。`)});
      const restore=el('button','恢复','button subtle danger small');restore.type='button';restore.disabled=busy || !!row.invalid;restore.onclick=()=>confirmMaintenance('restore',row.name);
      actions.append(verify,restore);item.append(text,actions);list.append(item)}
  }
  function confirmMaintenance(action,name) {
    if(!native()){toast('备份恢复请在桌面程序中操作。',true);return}if(busy)return;
    pending={action,name};$('#maintenance-title').textContent=action==='backup'?'创建完整快照':'恢复所选快照';
    $('#maintenance-detail').textContent=action==='backup'?'将临时停止聊天，复制JSONL与媒体并生成SHA256清单。完成后重新启动聊天、保持暂停，请手动恢复只回复。QQ登录保持。':`恢复 ${name}。先校验SHA256，替换前保留现有data。完成后聊天保持停止，需检查QQ补课游标后再启动。当前配置不会被覆盖。`;
    $('#restore-confirm-wrap').hidden=action!=='restore';$('#restore-confirm').value='';$('#maintenance-result').textContent='';$('#maintenance-run').disabled=false;$('#maintenance-run').textContent=action==='backup'?'确认创建备份':'确认恢复';$('#maintenance-dialog').showModal();
  }
  async function runMaintenance() {
    if(!pending || busy)return;
    if(pending.action==='restore' && $('#restore-confirm').value!=='恢复')throw Error('请输入“恢复”确认本次操作');
    busy=true;$('#maintenance-run').disabled=true;$('#maintenance-close').disabled=true;$('#maintenance-result').textContent='正在处理，请保持程序运行…';
    try{const result=await native().maintenance(pending.action,pending.name || null,pending.action);$('#maintenance-result').textContent=result.message || '操作完成';toast(result.message || '操作完成');await refreshBackups();await window.DFY.poll(true)}
    catch(e){$('#maintenance-result').textContent=String(e.message || e);throw e}
    finally{busy=false;$('#maintenance-close').disabled=false;await refreshBackups()}
  }
  async function diagnose(exportFile=false) {
    if(!native())throw Error('只读诊断请在桌面程序中运行');
    $('#program-diagnostics').textContent='正在读取本机运行状态…';
    const result=await native().maintenance(exportFile?'export_diagnostics':'diagnostics');
    $('#program-diagnostics').textContent=JSON.stringify(exportFile?result.report:result,null,2);
    if(exportFile)toast('诊断已导出：'+result.path);
  }
  function showExit() {if(!native()){toast('窗口管理请在桌面程序中使用。',true);return}$('#exit-dialog').showModal()}
  async function exit(action) {await native().window_action(action);if(action==='hide')$('#exit-dialog').close()}
  async function init() {
    $('#program-supervise').onclick=()=>guard(async()=>{const result=await window.DFY.api('supervision');$('#program-supervision-output').textContent=JSON.stringify(result,null,2);$('#program-supervision-output').hidden=false});
    $('#program-form').onsubmit=e=>guard(()=>save(e));
    $('#program-form').addEventListener('input',()=>{dirty=true});
    for(const id of ['program-theme','program-font_scale'])$('#'+id).onchange=()=>appearance({theme:$('#program-theme').value,font_scale:Number($('#program-font_scale').value)});
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{if(latest?.settings.theme==='system')appearance(latest.settings)});
    $('#program-backup').onclick=()=>confirmMaintenance('backup');$('#maintenance-run').onclick=()=>guard(runMaintenance);
    $('#maintenance-close').onclick=()=>{if(!busy)$('#maintenance-dialog').close()};$('#maintenance-dialog').addEventListener('cancel',e=>{if(busy)e.preventDefault()});
    $('#program-diagnose').onclick=()=>guard(()=>diagnose());$('#program-export-diagnostics').onclick=()=>guard(()=>diagnose(true));
    $('#program-refresh-backups').onclick=()=>guard(refreshBackups);$('#program-exit').onclick=showExit;$('#close-exit').onclick=()=>$('#exit-dialog').close();
    document.querySelectorAll('[data-window-action]').forEach(b=>b.onclick=()=>guard(()=>exit(b.dataset.windowAction)));
    $('#maintenance-pause').onclick=()=>guard(async()=>{await window.DFY.api('safety',{mode:'paused'});await window.DFY.poll(true);toast('全部暂停已生效。')});
    document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key.toLowerCase()==='q'){e.preventDefault();showExit()}if(e.key==='F5'){e.preventDefault();guard(()=>window.DFY.poll(true))}});
    await guard(refresh);
  }
  window.SystemUI={init,refresh,appearance,showExit};
})();
