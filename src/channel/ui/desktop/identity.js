'use strict';
(() => {
  const $=s=>document.querySelector(s),D=()=>window.DFY,native=()=>window.pywebview?.api;
  let saved=null,base=null,pending={},dirty=false,busy=false,reading=null;
  function display(profile){
    D().state.identity=profile;
    const name=profile.nickname;
    document.querySelectorAll('[data-product-name]').forEach(e=>{e.textContent=profile.product_name||'QQ ChatBot';e.title=e.textContent});
    document.querySelectorAll('[data-character-name]').forEach(e=>{e.textContent=name;e.title=name});
    for(const [selector,value]of [['[data-identity-icon]',profile.icon_data],['[data-identity-portrait]',profile.portrait_data]]){
      document.querySelectorAll(selector).forEach(e=>{if(value)e.src=value;e.alt=name});
    }
    document.title=profile.window_title||profile.product_name||'QQ ChatBot';
    if(D().state.page==='chat')$('#page-title').textContent='和'+name+'聊一会儿';
    $('#chat-input').placeholder='和'+name+'说句话，或粘贴一张图片…';
    $('#identity-typing-text').textContent=name+'正在想怎么回你';
    $('#identity-qr-title').textContent='让'+name+'回到 QQ';
    $('#analyze-sticker').textContent='让'+name+'看看';
    $('#soul-editor').placeholder='写下你希望'+name+'成为的样子…';
    D().state.lastChatHash='';D().renderChat();
  }
  function status(message){
    $('#identity-save').disabled=busy||!saved||!dirty;
    $('#identity-save').textContent=busy?'保存中…':'保存角色资料';
    if(message)$('#identity-status').textContent=message;
  }
  function fill(profile){
    base=profile.revision;pending={};dirty=false;
    $('#identity-nickname').value=profile.nickname;$('#identity-nickname').maxLength=profile.limits.max_nickname_chars;
    $('#identity-description').value=profile.appearance;$('#identity-description').maxLength=profile.limits.max_appearance_chars;
    for(const kind of ['portrait','icon']){
      const image=$('#identity-'+kind+'-preview');
      if(profile[kind+'_data'])image.src=profile[kind+'_data'];
      image.alt=kind==='icon'?'程序图标预览':'角色形象预览';
    }
    $('#identity-limit').textContent='静态 PNG / JPG / WEBP，单张 ≤ '+(profile.limits.max_image_bytes/1048576).toLocaleString()+' MB；图标也支持 ICO。';
    status('修改会在保存后应用。昵称进入后续对话，形象图与程序图标可以分别设置。');
  }
  async function refresh(force=false){
    if(reading)return reading;
    reading=(async()=>{
      const data=await D().api('identity'+(saved&&!force?'?revision='+encodeURIComponent(saved.revision):''));
      if(data.unchanged)return;
      saved=data;display(data);
      if(!dirty||force)fill(data);else status('其他窗口已更新角色；当前编辑保留，重新读取后再合并。');
    })();
    try{await reading}finally{reading=null}
  }
  function changed(){dirty=true;status('有未保存的角色修改。')}
  function choose(kind){$('#identity-'+kind+'-file').click()}
  async function file(kind,event){
    const f=event.target.files[0];event.target.value='';if(!f)return;
    if(!saved)await refresh();
    if(f.size>saved.limits.max_image_bytes)throw Error('图片超出单张大小限制');
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('图片读取失败'));reader.readAsDataURL(f)});
    pending[kind]=data;$('#identity-'+kind+'-preview').src=data;changed();
  }
  function reset(kind){
    if(!saved)return;pending[kind]=null;
    if(saved.defaults.image_data)$('#identity-'+kind+'-preview').src=saved.defaults.image_data;
    changed();
  }
  async function save(event){
    event.preventDefault();if(!saved||busy)return;busy=true;status('正在保存角色资料…');
    try{
      const result=await D().api('identity',{nickname:$('#identity-nickname').value.trim(),appearance:$('#identity-description').value,expected_revision:base,...pending});
      saved=result;display(result);fill(result);
      if(native()){
        try{await native().refresh_identity();status('已保存；界面、窗口、托盘与快捷方式已刷新，下一轮对话使用新昵称。')}
        catch(error){status('角色已保存，系统图标刷新尚未完成；桌面会自动重试。');D().toast('系统图标刷新未完成：'+String(error?.message||error),true)}
      }else status('已保存。正在运行的桌面程序会自动同步窗口和图标。');
      D().toast('角色资料已保存。');
    }finally{busy=false;status()}
  }
  function init(){
    $('#identity-form').onsubmit=e=>D().guard(()=>save(e));
    $('#identity-nickname').oninput=changed;$('#identity-description').oninput=changed;
    for(const kind of ['portrait','icon']){
      $('#identity-'+kind+'-choose').onclick=()=>choose(kind);
      $('#identity-'+kind+'-file').onchange=e=>D().guard(()=>file(kind,e));
      $('#identity-'+kind+'-reset').onclick=()=>reset(kind);
    }
    $('#identity-reload').onclick=()=>D().guard(async()=>{if(dirty&&!confirm('丢弃未保存的角色修改，重新读取？'))return;await refresh(true)});
    $('#identity-default').onclick=()=>{if(!saved)return;$('#identity-nickname').value=saved.defaults.nickname;$('#identity-description').value='';reset('portrait');reset('icon');status('默认设置已填入，点击保存后应用。')};
  }
  window.IdentityUI={init,refresh};
})();
