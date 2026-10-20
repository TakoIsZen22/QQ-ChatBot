'use strict';
(() => {
  const $=s=>document.querySelector(s),D=()=>window.DFY,native=()=>window.pywebview?.api;
  const el=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node};
  let current=null;
  function inline(parent,text){
    for(const part of text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g)){
      if(part.startsWith('**')&&part.endsWith('**'))parent.append(el('strong',part.slice(2,-2)));
      else if(part.startsWith('`')&&part.endsWith('`'))parent.append(el('code',part.slice(1,-1)));
      else{const link=/^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);parent.append(document.createTextNode(link?link[1]+'（'+link[2]+'）':part))}
    }
  }
  function render(guide){
    const box=$('#guide-content');box.replaceChildren();let code=null,list=null;
    for(const line of guide.text.split(/\r\n?|\n/)){
      if(line.trim().startsWith('```')){list=null;if(code){box.append(code);code=null}else code=el('pre','');continue}
      if(code){code.textContent+=line+'\n';continue}
      if(!line.trim()){list=null;continue}
      if(/^!\[/.test(line)&&guide.image_data){const image=el('img');image.src=guide.image_data;image.alt='Magpie 可选接入五步示意';image.className='guide-illustration';box.append(image);continue}
      const heading=/^(#{1,3})\s+(.+)$/.exec(line);
      if(heading){list=null;if(heading[1].length>1){const h=el('h3');inline(h,heading[2]);box.append(h)}continue}
      const item=/^\s*(?:[-*]|\d+\.)\s+(.+)$/.exec(line);
      if(item){if(!list){list=el('ul');box.append(list)}const li=el('li');inline(li,item[1]);list.append(li);continue}
      list=null;const p=el('p');inline(p,line);box.append(p);
    }
    if(code)box.append(code);
  }
  async function open(name){
    current=native()?.guide?await native().guide(name):await D().api('guide/'+encodeURIComponent(name));
    $('#guide-title').textContent=current.title;render(current);$('#guide-open-file').hidden=!native();
    $('#guide-official').hidden=name!=='magpie'||!native();$('#guide-dialog').showModal();$('#guide-content').scrollTop=0;
  }
  function init(){
    document.querySelectorAll('[data-guide]').forEach(button=>button.onclick=()=>D().guard(()=>open(button.dataset.guide)));
    $('#guide-close').onclick=()=>$('#guide-dialog').close();
    $('#guide-open-file').onclick=()=>D().guard(()=>native().open_target(current.file_target));
    $('#guide-official').onclick=()=>D().guard(()=>native().open_target('magpie_official_docs'));
  }
  window.GuideUI={init,open,render};
})();
