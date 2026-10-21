'use strict';
// QQNT password contract adapter. Only transient hashes/challenges live here.
const crypto = require('node:crypto');

function officialUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && !u.username && !u.password && !u.port &&
      (u.hostname === 'qq.com' || u.hostname.endsWith('.qq.com') || u.hostname.endsWith('.gtimg.com')) &&
      value.length <= 8192 ? value : '';
  } catch {return '';}
}

function passwordLogin(login, policy, hooks, now = Date.now) {
  let pending = null, running = false, stalled = false, generation = 0, timer;
  const attempts = [];
  const limits = policy.compatibility.limits || {};
  const timeout = limits.password_timeout_ms || 120000;
  const publish = phase => hooks.report({phase, online: false});
  function clear() {generation++;pending = null;clearTimeout(timer);timer = null;}
  function fail(phase = 'password_failed') {clear();publish(phase);}
  function waiting() {return pending !== null;}
  async function invoke(step, extras = {}) {
    const request = pending, run = generation;
    if (!request || running) throw Error('login_busy');
    running = true;
    delete pending.kind;delete pending.url;delete pending.challenge_id;
    let deadline;
    publish('password_authenticating');
    try {
      const operation = login.passwordLogin({uin: policy.bot, passwordMd5: request.hash, step,
        newDeviceLoginSig: new Uint8Array(), proofWaterSig: new Uint8Array(),
        proofWaterRand: new Uint8Array(), proofWaterSid: new Uint8Array(),
        unusualDeviceCheckSig: new Uint8Array(), ...extras});
      const result = await Promise.race([operation, new Promise((_, reject) => {
        deadline = setTimeout(() => {stalled = true;reject(Error('login_timeout'));}, timeout);
      })]);
      if (run !== generation || !pending || hooks.online()) return {phase: hooks.online() ? 'ready' : 'login_cancelled'};
      const code = String(result?.result), info = result?.loginErrorInfo;
      if (code === '0') {publish('password_accepted');return {phase: 'password_accepted'};}
      if (code === '140022008' && officialUrl(info?.proofWaterUrl)) {
        pending.kind = 'captcha';pending.url = officialUrl(info.proofWaterUrl);pending.challenge_id = crypto.randomUUID();
        publish('password_captcha');return {phase: 'password_captcha'};
      }
      if (['140022010', '140022011'].includes(code) && officialUrl(info?.jumpUrl) &&
          typeof info?.newDevicePullQrCodeSig === 'string' && info.newDevicePullQrCodeSig.length <= 8192 && info.newDevicePullQrCodeSig) {
        pending.kind = 'device';pending.url = officialUrl(info.jumpUrl);pending.signature = info.newDevicePullQrCodeSig;pending.challenge_id = crypto.randomUUID();
        publish('password_device');return {phase: 'password_device'};
      }
      fail();return {phase: 'password_failed'};
    } catch {if (run === generation && pending) fail(stalled ? 'password_expired' : 'password_failed');return {phase: hooks.online() ? 'ready' : stalled ? 'password_expired' : 'password_failed'};}
    finally {clearTimeout(deadline);running = false;}
  }
  async function action(body) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) throw Error('invalid_request');
    if (body.action === 'cancel') {clear();return {phase: 'login_cancelled'};}
    if (body.action === 'challenge') {
      if (!pending?.kind || running) throw Error('challenge_unavailable');
      return {kind: pending.kind, url: pending.url, challenge_id: pending.challenge_id}; // Authenticated IPC only; never state/logs.
    }
    if (body.action === 'password') {
      if (hooks.online()) throw Error('already_logged_in');
      if (stalled) throw Error('login_restart_required');
      if (running || hooks.initializing()) throw Error('login_busy');
      if (typeof login.passwordLogin !== 'function') throw Error('password_unsupported');
      if (Object.keys(body).some(k => !['action','uin','password_md5'].includes(k)) || body.uin !== policy.bot ||
          typeof body.password_md5 !== 'string' || !/^[a-f0-9]{32}$/.test(body.password_md5)) throw Error('invalid_request');
      const time = now(), windowMs = limits.login_window_ms || 600000;
      while (attempts.length && time - attempts[0] >= windowMs) attempts.shift();
      if (attempts.length >= (limits.login_max_attempts || 5) ||
          (attempts.length && time - attempts.at(-1) < (limits.login_min_interval_ms || 5000))) throw Error('login_rate_limited');
      attempts.push(time);clear();
      pending = {hash: body.password_md5};
      timer = setTimeout(() => {if (pending) fail('password_expired');}, timeout);timer.unref?.();
      return invoke(0);
    }
    if (body.action === 'continue') {
      if (!pending || running || hooks.online()) throw Error('challenge_unavailable');
      if (body.challenge_id !== pending.challenge_id || !pending.challenge_id) throw Error('challenge_unavailable');
      if (pending.kind === 'device') return invoke(2, {newDeviceLoginSig: new TextEncoder().encode(pending.signature)});
      if (pending.kind !== 'captcha' || typeof body.ticket !== 'string' || !body.ticket || body.ticket.length > 4096 ||
          typeof body.randstr !== 'string' || !body.randstr || body.randstr.length > 1024) throw Error('invalid_request');
      const sid = new URL(pending.url).searchParams.get('sid') || '';
      return invoke(1, {proofWaterSig: new TextEncoder().encode(body.ticket),
        proofWaterRand: new TextEncoder().encode(body.randstr), proofWaterSid: new TextEncoder().encode(sid)});
    }
    throw Error('invalid_request');
  }
  return {action, clear, waiting, failed() {if (pending) fail();}};
}

function authorized(actual, expected) {
  return typeof actual === 'string' && typeof expected === 'string' && expected.length >= 32 &&
    Buffer.byteLength(actual) === Buffer.byteLength(expected) &&
    crypto.timingSafeEqual(Buffer.from(actual), Buffer.from(expected));
}
module.exports = {passwordLogin, officialUrl, authorized};
