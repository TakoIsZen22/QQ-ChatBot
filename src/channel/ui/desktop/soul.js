'use strict';
(() => {
  const $=s=>document.querySelector(s),D=()=>window.DFY,native=()=>window.pywebview?.api;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  let current=null,revision=null,dirty=false,busy=false,loading=null,lastRead=0,draft=null,draftReady=Promise.resolve(),timer;
  async function persist(clear=false){
    const value=clear?null:{text:$('#soul-editor').value,revision};
    if(native())await native().ui_state({soul_draft:value});
    else if(clear)localStorage.removeItem('dfy.soul.draft');
    else localStorage.setItem('dfy.soul.draft',JSON.stringify(value));
  }
  function preview(){
    const box=$('#soul-preview');box.replaceChildren();let code=null;
    for(const line of $('#soul-editor').value.split('\n')){
      if(line.trim().startsWith('```')){if(code){box.append(code);code=null}else code=el('pre','');continue}
      if(code){code.textContent+=line+'\n';continue}
      const heading=/^(#{1,3})\s+(.+)$/.exec(line);
      if(heading)box.append(el(heading[1].length===1?'h2':'h3',heading[2]));
      else if(/^\s*[-*]\s+/.test(line))box.append(el('p','• '+line.replace(/^\s*[-*]\s+/,''),'soul-list-line'));
      else if(line.trim())box.append(el('p',line));
    }
    if(code)box.append(code);
    if(!box.childNodes.length)box.append(el('p','在左侧写下属于你的大肥鱼。留空保存时，只使用基础人设。','soul-muted'));
  }
  function status(message){
    $('#soul-counter').textContent=$('#soul-editor').value.length.toLocaleString()+' / '+(current?.limits.max_chars||12000).toLocaleString()+' 字';
    $('#soul-dirty').textContent=dirty?'有未保存修改':current?.active?'专属人设已启用':'尚未启用专属人设';
    $('#soul-save').disabled=busy||!current;
    if(message)$('#soul-status').textContent=message;
    preview();
  }
  function apply(data,allowDraft=false){
    current=data;revision=data.revision;$('#soul-editor').disabled=false;$('#soul-editor').maxLength=data.limits.max_chars;$('#soul-editor').value=data.text;
    $('#soul-path').textContent=data.path;$('#soul-open').disabled=!native()||!data.exists;
    dirty=false;
    if(allowDraft&&draft&&draft.text!==data.text){
      $('#soul-editor').value=draft.text;revision=draft.revision;dirty=true;
      $('#soul-status').textContent=revision===data.revision?'已恢复上次未保存的人设草稿。':'草稿已恢复，但磁盘版本已变化；可对照右侧当前文件，再合并保存。';
    }else $('#soul-status').textContent=data.active?'当前文件已接入对话；保存后从下一轮生效。':'可以导入 soul.md、填入模板，或直接编辑。';
    $('#soul-current-file').textContent=data.text||'当前文件为空，使用基础人设。';
    const history=$('#soul-history');history.replaceChildren();
    if(!data.history.length)history.append(el('p','首次保存后，这里会留下可恢复的版本。','soul-muted'));
    for(const row of data.history){
      const item=el('div',undefined,'soul-version'),meta=el('div');
      meta.append(el('strong',new Date(row.ts).toLocaleString('zh-CN')),el('small',row.chars+' 字 · '+row.revision.slice(0,10)));
      const b=el('button',row.revision===data.revision?'当前':'恢复','button secondary small');b.disabled=row.revision===data.revision;
      b.onclick=()=>D().guard(async()=>{
        if(!confirm('恢复这个版本？当前文件和未保存草稿会被替换，旧文件仍保留在历史中。'))return;
        busy=true;status();
        try{const next=await D().api('soul',{action:'restore',version_id:row.id,expected_revision:revision});draft=null;await persist(true);apply(next);D().toast('已恢复人设，下一轮对话生效。')}
        finally{busy=false;status()}
      });
      item.append(meta,b);history.append(item);
    }
    lastRead=Date.now();status();
  }
  async function refresh(force=false){
    await draftReady;
    if(loading)return loading;
    if(!force&&(dirty||Date.now()-lastRead<10000))return;
    loading=(async()=>{const data=await D().api('soul');if(!dirty||force)apply(data,!current)})();
    try{await loading}finally{loading=null}
  }
  async function save(e){
    e.preventDefault();if(busy||!current)return;busy=true;status('正在保存…');clearTimeout(timer);
    try{
      const data=await D().api('soul',{action:'save',text:$('#soul-editor').value,expected_revision:revision});
      draft=null;await persist(true);apply(data);D().toast(data.active?'专属人设已保存，下一轮对话生效。':'已停用专属层，下一轮使用基础人设。');
    }catch(error){status('未保存成功，编辑内容已保留。');throw error}
    finally{busy=false;status()}
  }
  function changed(){dirty=true;status('未保存修改仅是草稿，不会影响当前对话。');clearTimeout(timer);timer=setTimeout(()=>D().guard(()=>persist()),350)}
  function init(){
    draftReady=(async()=>{try{draft=native()?(await native().ui_state()).soul_draft:JSON.parse(localStorage.getItem('dfy.soul.draft')||'null')}catch{draft=null}})();
    $('#soul-form').onsubmit=e=>D().guard(()=>save(e));$('#soul-editor').oninput=changed;
    $('#soul-template').onclick=()=>D().guard(async()=>{await refresh();if(!current)return;if($('#soul-editor').value.trim()&&!confirm('用空白模板替换编辑区？尚未保存的修改会被替换。'))return;$('#soul-editor').value=current.template;changed()});
    $('#soul-reload').onclick=()=>D().guard(async()=>{if(dirty&&!confirm('丢弃未保存的草稿，重新读取磁盘文件？'))return;dirty=false;draft=null;await persist(true);await refresh(true)});
    $('#soul-import').onclick=()=>$('#soul-file').click();
    $('#soul-file').onchange=e=>D().guard(async()=>{const f=e.target.files[0];e.target.value='';if(!f)return;await refresh();if(!current)return;if(f.size>current.limits.max_bytes)throw Error('文件超出人设大小限制');const text=new TextDecoder('utf-8',{fatal:true}).decode(await f.arrayBuffer());if(text.length>current.limits.max_chars)throw Error('文件超出人设字数限制');if(dirty&&!confirm('导入会替换编辑区未保存的内容，继续？'))return;$('#soul-editor').value=text;changed();D().toast('已导入编辑区，点击保存才会应用。')});
    $('#soul-editor').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();D().guard(()=>save(e))}};
  }
  window.SoulUI={init,refresh};
})();
