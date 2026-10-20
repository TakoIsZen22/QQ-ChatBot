'use strict';
// 图片理解窗口只使用既有本机桥；识别、确认、放入对话分别由用户触发。
(() => {
  const $ = selector => document.querySelector(selector);
  const el = (tag, text, cls) => {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (cls) item.className = cls;
    return item;
  };
  let rows = [], current = null, selectedFile = null, attachment = null, busy = false, loading = false, meaningDirty = false;
  const api = (...args) => window.DFY.api(...args);
  const guard = fn => window.DFY.guard(fn);
  const toast = (...args) => window.DFY.toast(...args);
  const button = (text, fn, cls = 'button secondary small') => {
    const b = el('button', text, cls); b.type = 'button'; b.onclick = () => guard(fn); return b;
  };
  const image = (src, label) => { const i = el('img'); i.src = src; i.alt = label; return i; };

  function render() {
    const query = $('#sticker-search').value.trim().toLowerCase();
    const filtered = rows.filter(r => JSON.stringify([r.name,r.meaning,r.analysis]).toLowerCase().includes(query));
    $('#sticker-count').textContent = `${rows.length} 张 · ${rows.filter(r => r.meaning).length} 张已确认`;
    const library = $('#sticker-library'); library.replaceChildren();
    if (!filtered.length) {
      const empty = el('article', undefined, 'panel sticker-empty');
      empty.append(el('div', '✧', 'sticker-empty-symbol'), el('h2', rows.length ? '还没有找到这个梗' : '从你的第一张表情开始'),
        el('p', '导入一张常用表情，告诉她：这是在撒娇，还是在说反话。'), button('识别表情包', () => open(), 'button primary'));
      library.append(empty); return;
    }
    for (const row of filtered) {
      const meaning = row.meaning || row.analysis;
      const card = el('article', undefined, 'panel sticker-card');
      const preview = el('div', undefined, 'sticker-card-image');
      if (row.thumbnail) preview.append(image(row.thumbnail, row.meaning?.name || row.name));
      const body = el('div', undefined, 'sticker-card-body');
      body.append(el('span', row.meaning ? '你确认的含义' : '她的初步判断 · 待确认', 'tag ' + (row.meaning ? 'green' : 'gray')),
        el('h3', row.meaning?.name || row.name), el('p', meaning.intent || meaning.visual || '尚未记录含义'));
      const tags = el('div', undefined, 'sticker-tags');
      for (const t of (meaning.tags || []).slice(0,5)) tags.append(el('span', t, 'small-tag'));
      body.append(tags);
      const actions = el('div', undefined, 'sticker-card-actions');
      actions.append(button('查看 / 修正', () => open(row)), button('用于聊天', () => attach(row)));
      if (row.meaning) actions.append(button('清除含义', async () => {
        await api('sticker-intents', { action:'remove', media_id:row.media_id });
        await refresh(); toast('已清除确认含义。原图和历史修订仍保留供审计。');
      }, 'text-button'));
      body.append(actions); card.append(preview, body); library.append(card);
    }
  }
  async function refresh() {
    if (loading) return;
    loading = true;
    try { rows = await api('sticker-intents'); render(); window.DFY.renderChat(true); }
    catch (e) { $('#sticker-count').textContent = '表情库暂不可用，请检查聊天服务'; }
    finally { loading = false; }
  }
  function observation(row) {
    meaningDirty = false;
    const box = $('#sticker-analysis'); box.replaceChildren(el('strong', '她看到了什么'));
    const names = { visual:'画面', text:'文字', emotion:'情绪 / 语气', intent:'可能的意图', reply_hint:'接话建议', uncertainty:'歧义与不确定' };
    for (const [key, label] of Object.entries(names)) {
      if (!row.analysis?.[key]) continue;
      const line = el('div'); line.append(el('small', label), el('p', row.analysis[key])); box.append(line);
    }
    const m = row.meaning || row.analysis || {};
    $('#sticker-name').value = row.meaning?.name || row.name.replace(/\.[^.]+$/, '');
    $('#sticker-emotion').value = m.emotion || '';
    $('#sticker-intent').value = m.intent || '';
    $('#sticker-reply').value = m.reply_hint || '';
    $('#sticker-tags').value = (m.tags || []).join(', ');
    $('#sticker-meaning-form').hidden = false;
    $('#sticker-analysis-status').textContent = row.meaning ? '已确认。你可以继续修正，也可以放入对话。' : '这是模型推测。请按你的习惯修正，再确认。';
  }
  function open(row = null) {
    if (busy) { $('#sticker-dialog').showModal(); return; }
    current = row; selectedFile = null; $('#sticker-file').value = ''; $('#sticker-context').value = '';
    $('#sticker-meaning-form').hidden = !row;
    $('#sticker-preview').hidden = !row; $('#sticker-file-hint').hidden = !!row;
    $('#analyze-sticker').disabled = true;
    $('#sticker-analysis-status').textContent = '识别只分析图片，不会发出聊天消息。';
    if (row) { $('#sticker-preview').src = row.thumbnail; observation(row); }
    else { $('#sticker-preview').removeAttribute('src'); $('#sticker-analysis').replaceChildren(el('strong','先看看，再理解'),el('p','画面、文字、可能的情绪与歧义，会出现在这里。')); }
    if (!$('#sticker-dialog').open) $('#sticker-dialog').showModal();
  }
  async function choose(file) {
    if (!file || busy) return;
    const max = window.DFY.state.cfg?.stickers.max_image_bytes || 5242880;
    if (file.size > max) throw Error('图片超过大小限制：' + Math.round(max/1048576) + ' MB');
    if (!/^image\/(png|jpeg|webp|gif)$/.test(file.type)) throw Error('请选择 PNG、JPG、WEBP 或 GIF 图片');
    selectedFile = await new Promise((resolve,reject) => { const reader=new FileReader(); reader.onload=()=>resolve({name:file.name,url:reader.result});reader.onerror=()=>reject(Error('图片读取失败'));reader.readAsDataURL(file); });
    current = null; $('#sticker-preview').src = selectedFile.url; $('#sticker-preview').hidden = false;
    $('#sticker-file-hint').hidden = true; $('#sticker-meaning-form').hidden = true;
    $('#analyze-sticker').disabled = false;
    $('#sticker-analysis').replaceChildren(el('strong','图片已就绪'),el('p','可以补充语境，再让她看看。'));
    $('#sticker-analysis-status').textContent = '还没有调用视觉模型。';
  }
  async function analyze() {
    if (!selectedFile || busy) return;
    busy = true; $('#analyze-sticker').disabled = true; $('#sticker-file').disabled = true;
    $('#sticker-analysis-status').textContent = '正在通过你选择的视觉 API 观察画面、文字与语气…';
    try {
      current = await api('sticker-intents', {action:'analyze',data_url:selectedFile.url,name:selectedFile.name,context:$('#sticker-context').value});
      observation(current); await refresh();
    } catch (e) { $('#sticker-analysis-status').textContent = '本次未完成识别，可以重试。'; throw e; }
    finally { busy = false; $('#analyze-sticker').disabled = false; $('#sticker-file').disabled = false; }
  }
  async function save(event) {
    event.preventDefault(); if (!current) return;
    $('#save-sticker').disabled = true;
    try {
      current = await api('sticker-intents', {action:'save',media_id:current.media_id,name:$('#sticker-name').value,
        emotion:$('#sticker-emotion').value,intent:$('#sticker-intent').value,reply_hint:$('#sticker-reply').value,
        tags:$('#sticker-tags').value.split(/[,，]/).map(t=>t.trim()).filter(Boolean)});
      observation(current); await refresh(); toast('已经记住你使用这张表情的意思。');
    } finally { $('#save-sticker').disabled = false; }
  }
  function attach(row) {
    attachment = row; const box = $('#sticker-attachment'); box.replaceChildren(); box.classList.remove('hidden');
    box.append(image(row.thumbnail, '待发送图片'), el('span',(row.meaning?.name || row.name) + (row.image ? ' · 发送后自动识图' : row.meaning ? ' · 使用你确认的含义' : ' · 参考模型推测')),button('移除',clearAttachment,'text-button'));
    if ($('#sticker-dialog').open) $('#sticker-dialog').close();
    window.DFY.navigate('chat'); $('#chat-input').focus(); toast(row.image ? '图片已附加。发送后会自动看图并接话。' : '表情已放入输入框，点击发送后才进入对话。');
  }
  function clearAttachment(expected) { if(expected && attachment!==expected)return;attachment=null; $('#sticker-attachment').replaceChildren(); $('#sticker-attachment').classList.add('hidden'); }
  async function chooseChatImage(file) {
    if(!file)return;
    const max=window.DFY.state.cfg?.stickers.max_image_bytes || 5242880;
    if(file.size>max)throw Error('图片超过大小限制：'+Math.round(max/1048576)+' MB');
    if(!/^image\/(png|jpeg|webp|gif)$/.test(file.type))throw Error('请选择 PNG、JPG、WEBP 或 GIF 图片');
    const url=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('图片读取失败'));reader.readAsDataURL(file)});
    attach({name:file.name || '粘贴的图片',thumbnail:url,image:{data_url:url,name:file.name || '粘贴的图片'}});
  }
  function init() {
    $('#import-sticker').onclick=()=>open(); $('#close-sticker').onclick=()=>$('#sticker-dialog').close();
    $('#sticker-file').onchange=e=>guard(()=>choose(e.target.files[0]));
    $('#sticker-search').oninput=render;
    $('#analyze-sticker').onclick=()=>guard(analyze);
    $('#sticker-meaning-form').onsubmit=e=>guard(()=>save(e));
    $('#sticker-meaning-form').addEventListener('input',()=>{meaningDirty=true});
    $('#use-sticker').onclick=()=>{if(meaningDirty){toast('含义有尚未保存的修改，请先点击「确认并记住」。',true);return}if(current)attach(current)};
    $('#sticker-pause').onclick=()=>guard(async()=>{await api('safety',{mode:'paused'});await window.DFY.poll(true);toast('全部暂停已生效。')});
    $('#chat-sticker-picker').onclick=()=>window.DFY.navigate('stickers');
    $('#chat-image-picker').onclick=()=>$('#chat-image-file').click();
    $('#chat-image-file').onchange=e=>{const file=e.target.files[0];e.target.value='';guard(()=>chooseChatImage(file))};
    $('#chat-input').addEventListener('paste',e=>{const file=[...(e.clipboardData?.files || [])].find(f=>f.type.startsWith('image/'));if(file){e.preventDefault();guard(()=>chooseChatImage(file))}});
    const chat=$('.conversation');chat.addEventListener('dragover',e=>{if([...e.dataTransfer.types].includes('Files'))e.preventDefault()});
    chat.addEventListener('drop',e=>{if(e.dataTransfer.files.length){e.preventDefault();guard(()=>chooseChatImage(e.dataTransfer.files[0]))}});
    const drop=$('#sticker-drop');drop.ondragover=e=>e.preventDefault();drop.ondrop=e=>{e.preventDefault();guard(()=>choose(e.dataTransfer.files[0]))};
    refresh();
  }
  window.StickerUI={init,refresh,open,choose,analyze,attach,chooseChatImage,clearAttachment,get attachment(){return attachment},thumbnail:id=>rows.find(r=>r.media_id===id)?.thumbnail};
})();
