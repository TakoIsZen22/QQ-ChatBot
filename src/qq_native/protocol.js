'use strict';

// QQNT identifiers stay strings until the boundary: message IDs can exceed 2^53.
const id = value => /^\d{5,12}$/.test(String(value)) ? String(value) : null;
function segments(elements, selfId, selfUid) {
  const result = [];
  for (const element of (Array.isArray(elements) ? elements : []).slice(0, 100)) {
    if (element.elementType === 1 && typeof element.textElement?.content === 'string') {
      const e = element.textElement;
      const target = [e.atNtUin, e.atUid, e.atNtUid].find(x => id(x)) ||
        (selfUid && [e.atUid, e.atNtUid].includes(selfUid) ? selfId : null);
      if (e.atType && target) result.push({type: 'at', data: {qq: String(target)}});
      else result.push({type: 'text', data: {text: e.content.slice(0, 8000)}});
    } else if (element.elementType === 6 && element.faceElement) {
      result.push({type: 'face', data: {id: String(element.faceElement.faceIndex ?? '')}});
    } else if (element.elementType === 2 && element.picElement) {
      // Never expose paths from the QQ profile or interpret image text as commands.
      const candidate = element.picElement.originImageUrl;
      let url;
      try { const parsed = new URL(candidate); if (parsed.protocol === 'https:' && !parsed.username && !parsed.password) url = parsed.href; } catch {}
      result.push({type: 'image', data: url ? {url} : {summary: '[图片：原生下载尚未实现]'}});
    } else if (element.elementType === 4) {
      result.push({type: 'text', data: {text: '[语音：原生下载尚未实现]'}});
    }
  }
  return result;
}

function message(raw, policy, selfId, selfUid) {
  if (!raw || typeof raw !== 'object' || !id(selfId) || raw.msgId == null) return null;
  const sender = id(raw.senderUin);
  if (!sender || sender === String(selfId)) return null;
  const group = raw.chatType === 2 ? id(raw.peerUin || raw.peerUid) : null;
  if (group ? !policy.groups.includes(group) : raw.chatType !== 1 || sender !== policy.owner) return null;
  const msgId = String(raw.msgId);
  if (!/^\d{1,30}$/.test(msgId)) return null;
  const time = Number(raw.msgTime);
  const event = {post_type: 'message', message_type: group ? 'group' : 'private',
    message_id: msgId, user_id: sender, self_id: String(selfId),
    time: Number.isFinite(time) ? time : Math.floor(Date.now() / 1000),
    sender: {user_id: sender, nickname: String(raw.sendNickName || '').slice(0, 80)},
    message: segments(raw.elements, selfId, selfUid)};
  if (group) event.group_id = group;
  return event;
}

function textRequest(params, owner) {
  if (!params || id(params.user_id) !== owner || Object.keys(params).some(key => !['user_id', 'message'].includes(key))) throw new Error('recipient_not_allowed');
  const parts = params.message;
  if (!Array.isArray(parts) || !parts.length || parts.length > 10) throw new Error('text_only');
  if (parts.some(part => part?.type !== 'text' || typeof part.data?.text !== 'string')) throw new Error('text_only');
  const text = parts.map(part => part.data.text).join('');
  if (!text.trim() || text.length > 8000) throw new Error('invalid_text');
  return text;
}

function groupTextRequest(params, groups) {
  if (!params || !groups.includes(id(params.group_id)) || Object.keys(params).some(k => !['group_id', 'message'].includes(k))) throw new Error('recipient_not_allowed');
  // Reuse strict plain-text validation; no native @all/media elements permitted.
  return textRequest({user_id: params.group_id, message: params.message}, String(params.group_id));
}

module.exports = {id, segments, message, textRequest, groupTextRequest};
