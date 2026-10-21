'use strict';
const {id, message, textRequest, groupTextRequest} = require('./protocol');

class NativeDriver {
  constructor(policy, emit, state) {
    this.policy = policy; this.emit = emit; this.state = state;
    this.selfId = null; this.online = false; this.service = null;
    this.ownerUid = null; this.sent = []; this.attached = new WeakSet();
    this.selfUid = null; this.observedGroups = new Set(); this.groupSent = new Map();
    this.replyGroups = []; this.groupLimit = 5;
  }
  login(result) {
    this.service = null;this.ownerUid = null;
    this.selfId = id(result?.uin);
    this.selfUid = typeof result?.uid === 'string' && /^u_[A-Za-z0-9_-]{1,80}$/.test(result.uid) ? result.uid : null;
    this.observedGroups.clear();
    this.online = this.selfId === this.policy.bot && this.selfId !== this.policy.owner;
    this.state({phase: this.online ? 'initializing' : 'account_mismatch', online: false});
    this.emit({post_type: 'meta_event', meta_event_type: 'heartbeat', status: {online: false}});
  }
  offline() {
    this.online = false; this.ownerUid = null;this.service = null;
    this.observedGroups.clear();
    this.state({phase: 'offline', online: false});
    this.emit({post_type: 'meta_event', meta_event_type: 'heartbeat', status: {online: false}});
  }
  attach(session) {
    if (!session || !this.online) return;
    const service = session.getMsgService();
    if (!service || typeof service.addKernelMsgListener !== 'function') throw new Error('unsupported_message_service');
    this.service = service;
    if (this.attached.has(session)) {this.ready();return;}
    this.attached.add(session);
    const receive = rows => {
      if (!this.online || this.service !== service) return;
      for (const raw of (Array.isArray(rows) ? rows : []).slice(0, 500)) {
        const event = message(raw, this.policy, this.selfId, this.selfUid);
        if (!event) continue;
        // UID is learned only from a validated message from the configured owner.
        if (event.message_type === 'private' && typeof raw.senderUid === 'string' && /^u_[A-Za-z0-9_-]{1,80}$/.test(raw.senderUid)) this.ownerUid = raw.senderUid;
        if (event.message_type === 'group') this.observedGroups.add(event.group_id);
        this.emit(event);
      }
    };
    service.addKernelMsgListener(new Proxy({onRecvMsg: receive}, {get: (target, key) => key === 'then' ? undefined : Object.hasOwn(target,key) ? target[key] : (() => {})}));
    this.ready();
  }
  ready() {
    const online = this.online && !!this.service;
    this.state({phase: online ? 'ready' : 'waiting_login', online});
    // Login/reconnect must not wait for the periodic 15-second liveness heartbeat.
    this.emit({post_type: 'meta_event', meta_event_type: 'heartbeat', status: {online}});
  }
  async action(name, params = {}) {
    if (name === 'configure_groups') {
      if (!params || Object.keys(params).some(k => !['groups','group_per_minute'].includes(k)) || !Array.isArray(params.groups) || params.groups.length > 12 ||
          params.groups.some(g => !g || Object.keys(g).sort().join(',') !== 'group_id,reply_enabled' || !id(g.group_id) || typeof g.reply_enabled !== 'boolean') ||
          new Set(params.groups.map(g=>String(g.group_id))).size !== params.groups.length || !Number.isInteger(params.group_per_minute) || params.group_per_minute < 1 || params.group_per_minute > 19) throw new Error('invalid_request');
      this.policy.groups = params.groups.map(g=>String(g.group_id));
      this.replyGroups = params.groups.filter(g=>g.reply_enabled).map(g=>String(g.group_id));
      this.observedGroups = new Set([...this.observedGroups].filter(g=>this.policy.groups.includes(g)));
      this.groupLimit = Math.min(5, params.group_per_minute);
      return {configured: true};
    }
    if (name === 'get_status') return {online: this.online && !!this.service, good: !!this.service};
    if (name === 'get_login_info') {
      if (!this.online) throw new Error('not_logged_in');
      return {user_id: this.selfId, nickname: 'QQ ChatBot'};
    }
    if (!['send_private_msg','send_group_msg'].includes(name)) throw new Error('unsupported_action');
    const group = name === 'send_group_msg';
    const target = group ? id(params.group_id) : this.policy.owner;
    const text = group ? groupTextRequest(params, this.replyGroups) : textRequest(params, this.policy.owner);
    if (!this.online || !this.service) throw new Error('not_ready');
    if (!group && !this.ownerUid) throw new Error('owner_must_message_first');
    if (group && !this.observedGroups.has(target)) throw new Error('group_must_message_first');
    const now = Date.now();
    const bucket = (group ? this.groupSent.get(target) || [] : this.sent).filter(ts => now - ts < 60000);
    if (bucket.length >= (group ? this.groupLimit : 20)) throw new Error('rate_limited');
    // Consumed even if the native call times out: never retry an ambiguous send.
    bucket.push(now);
    if (group) this.groupSent.set(target, bucket); else this.sent = bucket;
    const result = await this.service.sendMsg('0', {chatType: group ? 2 : 1, peerUid: group ? target : this.ownerUid},
      [{elementType: 1, elementId: '', textElement: {content: text, atType: 0, atUid: '', atTinyId: '', atNtUid: ''}}], new Map());
    if (result?.result !== 0) throw new Error('native_send_failed');
    return {accepted: true};
  }
}
module.exports = {NativeDriver};
