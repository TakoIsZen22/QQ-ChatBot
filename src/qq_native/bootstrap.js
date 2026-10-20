'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {NativeDriver} = require('./driver');
const {gateway} = require('./gateway');
const {id} = require('./protocol');

function install(config) {
  if (!id(config.owner) || !id(config.bot) || config.owner === config.bot || !Array.isArray(config.groups) || config.groups.some(value => !id(value))) throw new Error('invalid_native_policy');
  if (!Number.isInteger(config.port) || config.port < 1024 || config.port > 65535) throw new Error('invalid_native_port');
  const directory = path.resolve(config.directory);
  fs.mkdirSync(directory, {recursive: true});
  function state(value) {
    const record = {schema: 'qq-chatbot.native.v1', ...value, time: new Date().toISOString()};
    const pending = path.join(directory, 'state.tmp');
    try {
      fs.writeFileSync(pending, JSON.stringify(record));
      fs.renameSync(pending, path.join(directory, 'state.json'));
    } catch { /* An unavailable diagnostics file must not interrupt the official app. */ }
  }
  let bridge;
  const driver = new NativeDriver(config, event => bridge?.emit(event), state);
  bridge = gateway(driver, config);
  const originalDlopen = process.dlopen;
  let hooked = false, session, sessionReady = false;
  bridge.listen().then(() => {if (!hooked) state({phase: 'waiting_kernel', online: false});}).catch(() => state({phase: 'port_unavailable', online: false}));
  const methods = (target, override) => new Proxy(Object.create(null), {get: (_, key) => key in override ? override[key] : typeof target[key] === 'function' ? target[key].bind(target) : target[key]});
  const attach = () => {
    if (sessionReady && driver.online) {
      try {driver.attach(session);} catch {state({phase: 'unsupported_session', online: false});}
    }
  };
  process.dlopen = function(module, filename, ...args) {
    const result = originalDlopen.call(this, module, filename, ...args);
    if (hooked || path.basename(String(filename)).toLowerCase() !== 'wrapper.node') return result;
    hooked = true;
    process.dlopen = originalDlopen;
    const api = module.exports;
    if (!api?.NodeIQQNTWrapperSession?.create || !api?.NodeIKernelLoginService?.get) {
      state({phase: 'unsupported_kernel', online: false}); return result;
    }
    const watchedLogin = new WeakSet();
    const login = methods(api.NodeIKernelLoginService, {get(...params) {
      const service = api.NodeIKernelLoginService.get(...params);
      if (watchedLogin.has(service)) return service;
      watchedLogin.add(service);
      const callbacks = {
        onQRCodeGetPicture(value) {
          const base64 = value?.pngBase64QrcodeData;
          if (typeof base64 !== 'string' || base64.length > 2097152) return;
          const png = Buffer.from(base64.replace(/^data:image\/png;base64,/, ''), 'base64');
          if (!png.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) return;
          try {fs.writeFileSync(path.join(directory, 'qrcode.png'), png);} catch {state({phase: 'qr_unavailable', online: false});return;}
          state({phase: 'waiting_qrcode', online: false});
        },
        onQRCodeSessionUserScaned() {state({phase: 'qrcode_scanned', online: false});},
        onQRCodeSessionFailed() {driver.offline();},
        onLoginFailed() {driver.offline(); state({phase: 'login_failed', online: false});},
        onQRCodeLoginSucceed(value) {driver.login(value); attach();},
        onLoginDisConnected() {driver.offline();},
        onLogoutSucceed() {driver.offline();},
      };
      service.addKernelLoginListener(new Proxy(callbacks, {get: (target, key) => target[key] || (() => {})}));
      return service;
    }});
    const sessions = methods(api.NodeIQQNTWrapperSession, {create(...params) {
      const native = api.NodeIQQNTWrapperSession.create(...params);
      session = native; sessionReady = false; driver.service = null; driver.ownerUid = null;
      return methods(native, {init(...params) {
        const original = params[3];
        if (original && typeof original === 'object') {
          params[3] = methods(original, {onOpentelemetryInit(...values) {
            original.onOpentelemetryInit?.(...values);
            if (values[0]?.is_init) {sessionReady = true; attach();}
          }});
        }
        return native.init(...params);
      }});
    }});
    module.exports = methods(api, {NodeIKernelLoginService: login, NodeIQQNTWrapperSession: sessions});
    state({phase: 'kernel_attached', online: false});
    return result;
  };
  return {driver, bridge};
}
module.exports = {install};
