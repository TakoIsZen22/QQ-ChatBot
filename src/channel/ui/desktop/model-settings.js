'use strict';
(() => {
  const $=s=>document.querySelector(s),D=()=>window.DFY;
  const MAGPIE='http://127.0.0.1:3425/v1';
  let drafts={},busy=false,previous='magpie';
  function value(){return {provider:$('#model-provider').value,base_url:$('#model-base-url').value.trim().replace(/\/+$/,''),key_env:$('#model-key-env').value.trim()}}
  function mode(){
    const magpie=$('#model-provider').value==='magpie';
    $('#model-base-url').readOnly=magpie;
    $('#model-api-hint').textContent=magpie?'Magpie 是可选接入方式。已有 Magpie 时复用本机网关；也可改选自有 API。':'直接使用你填写的 OpenAI 兼容 API，无需安装或启动 Magpie。';
    $('#model-gateway-address').textContent=$('#model-base-url').value||'尚未填写 API 地址';
  }
  function render(model){
    $('#model-provider').value=model.provider||'magpie';$('#model-base-url').value=model.base_url;$('#model-key-env').value=model.key_env;
    previous=$('#model-provider').value;
    drafts={};drafts[$('#model-provider').value]=value();mode();
  }
  function changed(){D().state.settingsDirty=true;$('#settings-note').textContent='有尚未保存的修改。';$('#model-connection-result').textContent='修改后可先检查连接，再保存设置并重启聊天。'}
  async function check(){
    if(busy)return;busy=true;const button=$('#load-models');button.disabled=true;button.textContent='正在检查…';
    $('#model-connection-result').textContent='正在读取所填 API 的模型清单；不发送聊天或人设。';
    try{
      const result=await D().api('model-connection',value());
      $('#model-options').replaceChildren(...result.models.map(m=>{const option=document.createElement('option');option.value=m.id;return option}));
      $('#model-connection-result').textContent='连接成功，读取到 '+result.models.length+' 个模型。'+(result.key_present?'核心进程已读取到所选密钥环境变量。':'未检测到密钥环境变量；若服务要求鉴权，请先配置。')+' 这项检查不代表已通过聊天、工具或视觉测试。';
      D().toast('API 连接检查通过，未修改已保存配置。');
    }catch(error){$('#model-connection-result').textContent='检查未通过：'+String(error?.message||error)+'。部分服务不提供模型清单，可手动填写模型 ID。';throw error}
    finally{busy=false;button.disabled=false;button.textContent='检查连接 / 读取模型'}
  }
  function init(){
    $('#model-provider').onchange=()=>{
      const selected=$('#model-provider').value;
      drafts[previous]={...value(),provider:previous};
      const next=drafts[selected]||{base_url:selected==='magpie'?MAGPIE:'',key_env:selected==='magpie'?'MAGPIE_API_KEY':'HARNESS_API_KEY'};
      $('#model-base-url').value=selected==='magpie'?MAGPIE:next.base_url;$('#model-key-env').value=next.key_env;previous=selected;mode();changed();
    };
    $('#model-base-url').oninput=()=>{mode();changed()};$('#model-key-env').oninput=changed;
    $('#load-models').onclick=()=>D().guard(check);
  }
  window.ModelUI={init,render,value,check};
})();
