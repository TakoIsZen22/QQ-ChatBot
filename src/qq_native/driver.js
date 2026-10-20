'use strict';
const {id, message, textRequest} = require('./protocol');

class NativeDriver {
  constructor(policy, emit, state) {
    this.policy = policy; this.emit = emit; this.state = state;
    this.selfId = null; this.online = false; this.service = null;
    this.ownerUid = null; this.sent = []; this.attached = new WeakSet();
  }
  login(result) {
    this.service = null;this.ownerUid = null;
    this.selfId = id(result?.uin);
    this.online = this.selfId === this.policy.bot && this.selfId !== this.policy.owner;
    this.state({phase: this.online ? 'initializing' : 'account_mismatch', online: false});
  }
  offline() {
    this.online = false; this.ownerUid = null;this.service = null;
    this.state({phase: 'offline', online: false});
    this.emit({post_type: 'meta_event', meta_event_type: 'heartbeat', status: {online: false}});
  }
  attach(session) {
    if (!session || !this.online) return;
    const service = session.getMsgService();
    if (!service || typeof service.addKernelMsgListener !== 'function') throw new Error('unsupported_message_service');
    this.service = service;
    if (this.attached.has(session)) {this.state({phase:'ready',online:true});return;}
    this.attached.add(session);
    const receive = rows => {
      if (!this.online || this.service !== service) return;
      for (const raw of (Array.isArray(rows) ? rows : []).slice(0, 500)) {
        const event = message(raw, this.policy, this.selfId);
        if (!event) continue;
        // UID is learned only from a validated message from the configured owner.
        if (event.message_type === 'private' && typeof raw.senderUid === 'string' && /^u_[A-Za-z0-9_-]{1,80}$/.test(raw.senderUid)) this.ownerUid = raw.senderUid;
        this.emit(event);
      }
    };
    service.addKernelMsgListener(new Proxy({onRecvMsg: receive}, {get: (target, key) => key === 'then' ? undefined : Object.hasOwn(target,key) ? target[key] : (() => {})}));
    this.state({phase: this.online ? 'ready' : 'waiting_login', online: this.online});
  }
  async action(name, params = {}) {
    if (name === 'get_status') return {online: this.online && !!this.service, good: !!this.service};
    if (name === 'get_login_info') {
      if (!this.online) throw new Error('not_logged_in');
      return {user_id: this.selfId, nickname: 'QQ ChatBot'};
    }
    if (name !== 'send_private_msg') throw new Error('unsupported_action');
    const text = textRequest(params, this.policy.owner);
    if (!this.online || !this.service) throw new Error('not_ready');
    if (!this.ownerUid) throw new Error('owner_must_message_first');
    const now = Date.now();
    this.sent = this.sent.filter(ts => now - ts < 60000);
    if (this.sent.length >= 20) throw new Error('rate_limited');
    // Consumed even if the native call times out: never retry an ambiguous send.
    this.sent.push(now);
    const result = await this.service.sendMsg('0', {chatType: 1, peerUid: this.ownerUid},
      [{elementType: 1, elementId: '', textElement: {content: text, atType: 0, atUid: '', atTinyId: '', atNtUid: ''}}], new Map());
    if (result?.result !== 0) throw new Error('native_send_failed');
    return {accepted: true};
  }
}
module.exports = {NativeDriver};
