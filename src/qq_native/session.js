'use strict';
// Independent QQNT adapter; no daily-QQ profile or saved-account discovery.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {id} = require('./protocol');
const {passwordLogin} = require('./password_login');

const callbacks = value => new Proxy(value, {get(target, key) {
  if (typeof key !== 'string' || key === 'then') return undefined;
  return Object.hasOwn(target, key) ? target[key] : () => {};
}});

function initialize(api, policy, driver, report) {
  if (!id(policy.owner) || !id(policy.bot) || policy.owner === policy.bot) throw new Error('invalid_accounts');
  const profile = path.resolve(policy.directory, 'profile');
  const global = path.join(profile, 'global');
  const account = path.join(profile, 'account');
  const downloads = path.join(profile, 'downloads');
  for (const dir of [global, account, downloads]) fs.mkdirSync(dir, {recursive: true});
  const version = policy.compatibility.version;
  const appid = policy.compatibility.appid;
  const system = os.release();
  const engine = api.NodeIQQNTWrapperEngine.get();
  const login = api.NodeIKernelLoginService.get();
  let session, startup, initializing = false, requested = false;
  let stopped = false, authenticated = null, messageReady = false;
  const password = passwordLogin(login, policy, {report, online: () => stopped || driver.online,
    initializing: () => initializing});
  const invalidate = (phase, codes = {}) => {
    if (stopped) return;
    driver.offline();
    report({phase, online: false, ...codes});
  };
  const qr = () => {
    if (stopped || driver.online || initializing || requested) return false;
    requested = true;
    report({phase: 'generating_qrcode', online: false});
    try {login.getQRCodePicture();} catch {requested = false; invalidate('qrcode_request_failed');}
    return true;
  };
  const attach = value => {
    if (stopped) return;
    password.clear();
    // Validate before creating an account session. A scanned owner/stranger never attaches.
    driver.login(value);
    if (!driver.online) {report({phase: 'account_mismatch', online: false});return;}
    if (initializing || stopped) return;
    if (typeof value.uid !== 'string' || !/^u_[A-Za-z0-9_-]{1,80}$/.test(value.uid)) {
      invalidate('invalid_login_result');return;
    }
    initializing = true; authenticated = value;
    try {
      startup = api.NodeIQQNTStartupSessionWrapper.create();
      session = api.NodeIQQNTWrapperSession.getNTWrapperSession('nt_1');
      const guid = login.getMachineGuid();
      if (typeof guid !== 'string' || !/^[a-fA-F0-9-]{16,64}$/.test(guid)) throw new Error('invalid_device_id');
      const cfg = {
        selfUin: String(value.uin), selfUid: value.uid,
        desktopPathConfig: {account_path: account}, clientVer: version,
        a2: '', d2: '', d2Key: '', machineId: '', platform: 3, platVer: system, appid,
        rdeliveryConfig: {appKey: '', systemId: 0, appId: '', logicEnvironment: '', platform: 3,
          language: '', sdkVersion: '', userId: '', appVersion: '', osVersion: '', bundleId: '', serverUrl: '', fixedAfterHitKeys: ['']},
        defaultFileDownloadPath: downloads,
        deviceInfo: {guid, buildVer: version, localId: 2052, devName: os.hostname(), devType: 'Windows_NT',
          vendorName: '', osVer: system, vendorOsName: 'Windows_NT', setMute: false, vendorType: 0},
        deviceConfig: JSON.stringify({appearance: {isSplitViewMode: true}, msg: {}}),
      };
      session.init(cfg, callbacks({onMSFStatusChange(status) {
        // Offline status is surfaced; no automatic account login or ambiguous-send retry.
        if (status === 1 && messageReady) invalidate('offline');
        if (status === 2 && messageReady && authenticated && !stopped) {driver.login(authenticated);driver.attach(session);}
      }}), callbacks({}), callbacks({onOpentelemetryInit(info) {
        if (stopped) return;
        if (info?.is_init !== true) {invalidate('session_init_failed');return;}
        try {messageReady = true;driver.login(authenticated);driver.attach(session);} catch {invalidate('unsupported_message_service');}
      }}));
      startup.start();
    } catch {invalidate('session_init_failed');}
  };
  engine.initWithDeskTopConfig({base_path_prefix: '', platform_type: 3, app_type: 4,
    app_version: version, os_version: system, use_xlog: false, qua: policy.compatibility.qua,
    global_path_config: {desktopGlobalPath: global}, thumb_config: {maxSide: 324, minSide: 48, longLimit: 6, density: 2}}, callbacks({}));
  login.initConfig({machineId: '', appid, platVer: system, commonPath: global,
    clientVer: version, hostName: os.hostname(), externalVersion: false});
  login.addKernelLoginListener(callbacks({
    onLoginConnected() {if (!requested && !driver.online && !stopped && !password.waiting()) qr();},
    onQRCodeGetPicture(value) {
      if (stopped || initializing || driver.online || password.waiting()) return;
      const encoded = value?.pngBase64QrcodeData;
      if (typeof encoded !== 'string' || encoded.length > 2097152) {invalidate('invalid_qrcode');return;}
      const png = Buffer.from(encoded.replace(/^data:image\/png;base64,/, ''), 'base64');
      if (!png.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) {invalidate('invalid_qrcode');return;}
      const file = path.join(policy.directory, 'qrcode.png');
      fs.writeFileSync(file + '.tmp', png); fs.renameSync(file + '.tmp', file);
      report({phase: 'waiting_qrcode', online: false});
    },
    onQRCodeSessionUserScaned() {if (!stopped && !password.waiting() && !initializing && !driver.online) report({phase: 'qrcode_scanned', online: false});},
    onQRCodeSessionFailed(type, code) {
      if (password.waiting() || initializing || driver.online || stopped) return;
      requested = false;
      invalidate(type === 1 && code === 3 ? 'qrcode_expired' : 'login_failed',
        {error_type: Number.isInteger(type) ? type : -1, error_code: Number.isInteger(code) ? code : -1});
    },
    onQRCodeLoginSucceed: attach,
    onLoginFailed() {requested = false;if (password.waiting()) password.failed();else invalidate('login_failed');},
    onPasswordLoginFailed() {if (!stopped && !initializing && !driver.online) password.failed();},
    // QR transport closes when ownership passes to the account session.
    onLoginDisConnected() {if (!initializing && !password.waiting()) {requested = false;invalidate('offline');}},
    onLogoutSucceed() {authenticated = null;messageReady = false;requested = false; invalidate('offline');},
  }));
  report({phase: 'connecting', online: false});
  login.connect();
  return {engine, login, password: body => password.action(body),
    refresh() {if (initializing || stopped) return false;password.clear();requested = false;return qr();},
    stop() {stopped = true;password.clear();driver.offline();}, profile, global, account};
}
module.exports = {initialize, callbacks};
