'use strict';
(() => {
 const $=s=>document.querySelector(s),D=()=>window.DFY;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n};
 let meta=null,selected='',layout='single',refreshing=false,working=false,initialized=false;
 const panes=new Map(),lastSeen={};
 try{selected=localStorage.getItem('qq-monitor-selected')||'';layout=localStorage.getItem('qq-monitor-layout')==='grid'?'grid':'single';Object.assign(lastSeen,JSON.parse(localStorage.getItem('qq-monitor-seen')||'{}'))}catch{}
 function persist(){try{localStorage.setItem('qq-monitor-selected',selected);localStorage.setItem('qq-monitor-layout',layout);localStorage.setItem('qq-monitor-seen',JSON.stringify(lastSeen))}catch{}}
 async function mutate(body){if(working)return;working=true;try{await D().api('group-monitor',body);await refresh();D().state.cfg=null;D().toast('监听设置已保存，立即生效。')}finally{working=false;for(const p of panes.values())p.toggle.disabled=false}}
 function renderTabs(){
  const tabs=$('#group-tabs');tabs.replaceChildren();
  for(const group of meta.groups){const b=el('button',undefined,'group-tab'+(selected===group.group_id?' active':''));b.type='button';b.setAttribute('role','tab');b.setAttribute('aria-selected',String(selected===group.group_id));
   b.append(el('span',group.name||'群 '+group.group_id),el('small',group.enabled?'监听中':'已停用'));
   if(group.last_message_id&&lastSeen[group.group_id]!==group.last_message_id)b.append(el('i','新','group-unread'));
   b.onclick=()=>{selected=group.group_id;persist();D().guard(refresh)};tabs.append(b)}
 }
 function createPane(group){
  const pane=el('article',undefined,'panel group-pane');pane.dataset.groupId=group.group_id;
  const head=el('header',undefined,'group-pane-head'),title=el('div'),name=el('h2'),sub=el('small'),tools=el('div',undefined,'group-pane-tools');title.append(name,sub);
  const toggle=el('button',undefined,'button secondary small');toggle.type='button';toggle.onclick=()=>D().guard(async()=>{const g=meta.groups.find(g=>g.group_id===group.group_id);await mutate({action:'update',group_id:g.group_id,name:g.name,enabled:!g.enabled})});
  const edit=el('button','备注','text-button');edit.type='button';edit.onclick=()=>openEdit(meta.groups.find(g=>g.group_id===group.group_id));
  const remove=el('button','移除','text-button');remove.type='button';remove.onclick=()=>{const g=meta.groups.find(g=>g.group_id===group.group_id);$('#group-remove-name').textContent=(g.name||'群')+' · '+g.group_id;$('#group-remove-dialog').dataset.groupId=g.group_id;$('#group-remove-dialog').showModal()};tools.append(toggle,edit,remove);head.append(title,tools);
  const body=el('div',undefined,'group-message-list');body.setAttribute('role','log');body.setAttribute('aria-label','群 '+group.group_id+' 消息');body.tabIndex=0;
  const bottom=el('button','有新消息 · 回到底部','button secondary small group-to-bottom');bottom.type='button';bottom.hidden=true;bottom.onclick=()=>{body.scrollTop=body.scrollHeight;bottom.hidden=true};
  body.onscroll=()=>{if(body.scrollHeight-body.scrollTop-body.clientHeight<48)bottom.hidden=true};
  const note=el('footer','只读监听 · 无发送入口 · 图片与语音仅显示类型标记');pane.append(head,body,bottom,note);
  const entry={pane,name,sub,toggle,body,bottom,hash:null};panes.set(group.group_id,entry);return entry;
 }
 function openEdit(group){$('#group-form').dataset.groupId=group?.group_id||'';$('#group-dialog-title').textContent=group?'修改群备注':'添加群聊监听';$('#group-number').value=group?.group_id||'';$('#group-number').readOnly=!!group;$('#group-name').value=group?.name||'';$('#group-dialog').showModal();(group?$('#group-name'):$('#group-number')).focus()}
 function renderMessages(p,group,rows){
  const hash=JSON.stringify(rows);if(hash===p.hash)return;
  const nearBottom=p.hash===null||p.body.scrollHeight-p.body.scrollTop-p.body.clientHeight<80,prior=p.body.scrollTop;
  p.hash=hash;const fragment=document.createDocumentFragment();
  for(const row of rows){const line=el('article',undefined,'group-message'),top=el('div',undefined,'group-message-meta'),timestamp=row.event_time?new Date(row.event_time*1000):new Date(row.ts);
   top.append(el('strong',row.sender_name||'群成员'),el('small',row.user_id),el('time',Number.isNaN(timestamp.getTime())?'时间未知':timestamp.toLocaleString('zh-CN',{timeZone:D().state.cfg?.awakening?.timezone||'Asia/Hong_Kong',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})));
   line.append(top,el('p',row.text||'[空消息]'));fragment.append(line)}
  if(!rows.length){fragment.append(el('div',group.enabled?'等待新消息。仅显示开启监听后收到的内容，不读取群历史。':'监听已停用。开启后接收新消息。','group-empty'))}
  p.body.replaceChildren(fragment);if(nearBottom){p.body.scrollTop=p.body.scrollHeight;p.bottom.hidden=true}else{p.body.scrollTop=prior;p.bottom.hidden=false}
 }
 async function refresh(){
  if(refreshing)return;refreshing=true;
  try{
   const next=await D().api('group-monitor');meta=next;
   $('#group-connection').textContent=!next.qq_enabled?'QQ 桥接未启用，请先完成 QQ 接入。':!next.connected||!next.online?'QQ 未连接，暂时收不到新消息；已有记录仍可查看。':'QQ 已连接 · 实时接收已开启的监听群';
   $('#group-connection').classList.toggle('disconnected',!next.qq_enabled||!next.connected||!next.online);
   $('#group-limit').textContent=next.groups.length+' / '+next.max_groups+' 个群 · 每窗最近 '+next.history_limit+' 条';$('#group-add').disabled=next.groups.length>=next.max_groups;
   $('#nav-groups').textContent=next.groups.filter(g=>g.enabled).length;
   if(!next.groups.some(g=>g.group_id===selected))selected=next.groups[0]?.group_id||'';
   const visible=layout==='grid'?next.groups:next.groups.filter(g=>g.group_id===selected),box=$('#group-windows');box.dataset.layout=layout;
   for(const [id,p]of panes){if(!next.groups.some(g=>g.group_id===id)){p.pane.remove();panes.delete(id)}else p.pane.hidden=!visible.some(g=>g.group_id===id)}
   $('#group-empty').hidden=!!next.groups.length;
   for(const group of visible){const p=panes.get(group.group_id)||createPane(group);if(!p.pane.isConnected)box.append(p.pane);p.pane.hidden=false;p.name.textContent=group.name||'群 '+group.group_id;p.sub.textContent=group.group_id+' · '+(group.enabled?'监听中':'已停用');p.toggle.textContent=group.enabled?'停用监听':'开启监听';p.toggle.disabled=working}
   await Promise.all(visible.map(async group=>{try{const data=await D().api('group-monitor?group_id='+encodeURIComponent(group.group_id));renderMessages(panes.get(group.group_id),group,data.messages);lastSeen[group.group_id]=group.last_message_id}catch(e){panes.get(group.group_id).sub.textContent='读取失败：'+String(e.message||e)}}));
   renderTabs();persist();$('#group-refresh-note').textContent='已更新 '+new Date().toLocaleTimeString('zh-CN');
   document.querySelectorAll('[data-group-layout]').forEach(b=>b.classList.toggle('active',b.dataset.groupLayout===layout));
  }catch(e){$('#group-connection').textContent='监听服务未连接，已有画面停止更新。请启动或重启聊天服务。';$('#group-connection').classList.add('disconnected');$('#group-refresh-note').textContent=String(e.message||e);throw e}finally{refreshing=false}
 }
 function init(){if(initialized)return;initialized=true;
  $('#group-add').onclick=()=>openEdit();$('#group-dialog-close').onclick=()=>$('#group-dialog').close();$('#group-refresh').onclick=()=>D().guard(refresh);
  $('#group-form').onsubmit=e=>{e.preventDefault();D().guard(async()=>{const existing=e.target.dataset.groupId;const body={action:existing?'update':'add',group_id:$('#group-number').value.trim(),name:$('#group-name').value.trim()};if(existing)body.enabled=meta.groups.find(g=>g.group_id===existing).enabled;await mutate(body);selected=body.group_id;$('#group-dialog').close();persist();await refresh()})};
  $('#group-remove-cancel').onclick=()=>$('#group-remove-dialog').close();$('#group-remove-confirm').onclick=()=>D().guard(async()=>{await mutate({action:'remove',group_id:$('#group-remove-dialog').dataset.groupId});$('#group-remove-dialog').close()});
  document.querySelectorAll('[data-group-layout]').forEach(b=>b.onclick=()=>{layout=b.dataset.groupLayout;persist();D().guard(refresh)});
  const poll=()=>{if(D().state.page==='groups'&&!document.hidden)refresh().catch(()=>{});setTimeout(poll,D().state.cfg?.desktop?.poll_interval_ms||2000)};setTimeout(poll,D().state.cfg?.desktop?.poll_interval_ms||2000);
 }
 window.GroupMonitorUI={init,refresh};
})();
