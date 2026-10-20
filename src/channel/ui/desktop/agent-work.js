'use strict';
(() => {
 const $=s=>document.querySelector(s),D=()=>window.DFY,N=()=>window.pywebview?.api;
 let latest=null,dirty=false,busy=false,refreshing=false,connection=null;
 const names={draft:'待你确认',queued:'待 Agent 接单',running:'Agent 处理中',cancel_requested:'已请求外部取消',cancelled:'已取消',completed:'Agent 已回执',failed:'处理未完成',interrupted:'中断待核对'};
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
 function mode(){const cli=$('#agent-transport').value==='cli';$('#agent-cli-fields').hidden=!cli;$('#agent-desktop-fields').hidden=cli}
 function renderBinding(binding){
  if(dirty)return;
  for(const k of ['name','transport','cwd','timeout_seconds'])$('#agent-'+k).value=binding[k];
  for(const k of ['enabled','notify_result'])$('#agent-'+k).checked=binding[k];
  $('#agent-command').value=JSON.stringify(binding.command,null,2);$('#agent-limits').value=JSON.stringify(binding,null,2);mode();
 }
 async function act(action,body={}){if(busy)return;busy=true;try{await D().api('agent-work',{action,...body});await refresh();D().toast({create:'工作已明确转交，等待外部 Agent。',approve:'已确认转交这条工作。',cancel:'取消状态已记录；桌面 Agent 需自行停止执行。'}[action])}finally{busy=false}}
 function renderTasks(tasks){
  const box=$('#agent-task-list');box.replaceChildren();
  if(!tasks.length){box.append(el('p','还没有转交工作。可以在这里填写，或在 QQ 私聊中发送“/工作 具体请求”。','program-muted'));return}
  for(const task of tasks){
   const card=el('article',undefined,'agent-task'),head=el('div',undefined,'agent-task-head');
   head.append(el('span',names[task.status]||task.status,'tag '+(task.status==='completed'?'green':task.status==='draft'?'amber':'gray')),el('small',task.task_id.slice(0,8)+' · '+task.agent_name+' · '+(task.origin==='qq'?'QQ':'本机')));card.append(head,el('pre',task.text));
   if(task.status==='draft'){const b=el('button','确认并转交原文','button primary small');b.disabled=!latest.binding.enabled||latest.paused;b.onclick=()=>D().guard(()=>act('approve',{task_id:task.task_id}));card.append(b)}
   if(['queued','running','draft'].includes(task.status)){const b=el('button',task.status==='running'&&task.transport==='desktop'?'请求外部 Agent 取消':'取消工作','button secondary small');b.onclick=()=>D().guard(()=>act('cancel',{task_id:task.task_id}));card.append(b)}
   if(task.detail)card.append(el('p',task.detail));
   if(task.result!==undefined){const detail=el('details');detail.open=true;detail.append(el('summary','外部 Agent 回执 · 未独立核实'),el('pre',task.result));card.append(detail)}
   if(task.status==='interrupted'||task.status==='failed')card.append(el('small','请先在外部 Agent 核对是否已执行；程序不会自动重试。'));
   box.append(card);
  }
 }
 async function refresh(){
  if(refreshing)return;refreshing=true;
  try{latest=await D().api('agent-work');renderBinding(latest.binding);renderTasks(latest.tasks);
   $('#agent-status').textContent=(latest.binding.enabled?'当前绑定：'+latest.binding.name+' · '+(latest.binding.transport==='cli'?'CLI':'桌面 Agent'):'工作转交未启用')+' · '+(latest.paused?'全部暂停中':'可转交')+' · 未完成 '+latest.active_count+' 项'+(latest.last_contact?' · 桌面端最近访问 '+new Date(latest.last_contact).toLocaleTimeString():'');
   $('#agent-submit').disabled=!latest.binding.enabled||latest.paused;$('#agent-new-text').maxLength=latest.binding.max_task_chars;
   if(!connection&&N()?.agent_connection){connection=await N().agent_connection();$('#agent-connection-config').textContent=JSON.stringify(connection,null,2)}
  }finally{refreshing=false}
 }
 async function save(event){
  event.preventDefault();let binding=JSON.parse($('#agent-limits').value);if(!binding||typeof binding!=='object'||Array.isArray(binding))throw Error('高级绑定参数必须是 JSON 对象');
  for(const k of ['name','transport','cwd'])binding[k]=$('#agent-'+k).value.trim();binding.timeout_seconds=Number($('#agent-timeout_seconds').value);
  binding.command=JSON.parse($('#agent-command').value);for(const k of ['enabled','notify_result'])binding[k]=$('#agent-'+k).checked;
  const button=$('#agent-save');button.disabled=true;
  try{await D().api('agent-binding',binding);dirty=false;await refresh();await D().poll(true);$('#agent-binding-note').textContent='绑定已保存并立即生效。保存不会启动 Agent，也不会执行任何测试任务。';D().toast('Agent 绑定已保存。')}finally{button.disabled=false}
 }
 function init(){
  $('#agent-binding-form').onsubmit=e=>D().guard(()=>save(e));$('#agent-binding-form').addEventListener('input',()=>{dirty=true;$('#agent-binding-note').textContent='有未保存的绑定修改。'});$('#agent-transport').onchange=mode;
  $('#agent-new-form').onsubmit=e=>{e.preventDefault();if(busy)return;D().guard(async()=>{await act('create',{text:$('#agent-new-text').value.trim()});$('#agent-new-text').value=''})};
  $('#agent-refresh').onclick=()=>D().guard(refresh);$('#agent-reload').onclick=()=>{dirty=false;D().guard(refresh)};
  $('#agent-guide').onclick=()=>D().guard(()=>window.GuideUI.open('agent'));
  $('#agent-copy-config').onclick=()=>D().guard(async()=>{if(!connection)throw Error('请在桌面端读取本机 MCP 配置');await navigator.clipboard.writeText(JSON.stringify(connection,null,2));D().toast('MCP 配置已复制。在桌面 Agent 中添加后，由你明确指示它领取工作。')});
  for(const [id,kind,target]of [['agent-pick-program','executable','agent-command'],['agent-pick-cwd','cwd','agent-cwd']])$('#'+id).onclick=()=>D().guard(async()=>{if(!N()?.agent_pick)throw Error('文件选择请在桌面端操作');const r=await N().agent_pick(kind);if(!r.path)return;$('#'+target).value=kind==='executable'?JSON.stringify([r.path],null,2):r.path;dirty=true});
  const button=el('button','转为工作请求','text-button');button.id='chat-forward-work';button.type='button';button.onclick=()=>{$('#agent-new-text').value=$('#chat-input').value;D().navigate('agent');$('#agent-new-text').focus()};document.querySelector('.composer-tools')?.prepend(button);
  setInterval(()=>{if(D().state.page==='agent')D().guard(refresh)},2500);
 }
 window.AgentWorkUI={init,refresh};
})();
