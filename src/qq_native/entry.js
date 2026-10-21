'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {NativeDriver} = require('./driver');
const {gateway} = require('./gateway');
const {initialize} = require('./session');
const {id} = require('./protocol');
const {resolveCompatibility} = require('./compatibility');

async function start(configFile) {
  const policy = JSON.parse(fs.readFileSync(configFile, 'utf8'));
  const root = path.resolve(__dirname, '../..');
  const directory = path.join(root, '.runtime/qq-native');
  if (policy.directory !== directory || !/^[a-f0-9]{32}$/.test(policy.run_id) ||
      !id(policy.owner) || !id(policy.bot) || policy.owner === policy.bot ||
      !Array.isArray(policy.groups) || policy.groups.some(x => !id(x)) ||
      !Number.isInteger(policy.port) || policy.port < 1024 || policy.port > 65535) throw new Error('invalid_policy');
  const compat = resolveCompatibility(JSON.parse(fs.readFileSync(path.join(root, 'config/qq-native-compat.json'), 'utf8')), policy, process.versions, root);
  policy.compatibility = compat;
  let bridge, lastPhase, session;
  const report = value => {
    const record = {schema: 'qq-chatbot.native.v2', run_id: policy.run_id, ...value, time: new Date().toISOString()};
    fs.writeFileSync(path.join(directory, 'state.tmp'), JSON.stringify(record));
    fs.renameSync(path.join(directory, 'state.tmp'), path.join(directory, 'state.json'));
    if (lastPhase !== value.phase) {
      fs.appendFileSync(path.join(directory, 'events.jsonl'), JSON.stringify({ts: record.time, level: value.phase.includes('failed') ? 'ERROR' : 'INFO', event: 'qq_native_phase', phase: value.phase, online: value.online, error_type: value.error_type, error_code: value.error_code}) + '\n');
      lastPhase = value.phase;
    }
  };
  const driver = new NativeDriver(policy, event => bridge?.emit(event), report);
  bridge = gateway(driver, policy, body => {
    if (!session) throw Error('not_ready');
    return session.password(body);
  });
  await bridge.listen(); // Port must be exclusively ours before a native login begins.
  report({phase: 'loading_kernel', online: false});
  const native = {exports: {}};
  process.dlopen(native, path.join(policy.client, 'resources/app/wrapper.node'));
  session = initialize(native.exports, policy, driver, report);
  const requests = path.join(directory, 'control.json');
  const timer = setInterval(() => {
    try {
      if (!fs.existsSync(requests) || fs.statSync(requests).size > 1024) return;
      const request = JSON.parse(fs.readFileSync(requests, 'utf8')); fs.unlinkSync(requests);
      if (request.run_id !== policy.run_id) return;
      if (request.action === 'refresh_qr') session.refresh();
      if (request.action === 'stop') {
        clearInterval(timer);session.stop();report({phase: 'stopped', online: false});
        bridge.close();setTimeout(() => process.exit(0), 500);
      }
    } catch {report({phase: 'control_failed', online: driver.online});}
  }, compat.limits.control_poll_ms);
  const runtime = {driver, session, bridge};
  globalThis[Symbol.for('QQChatBot.native')] = runtime;
  return runtime;
}
if (require.main === module) start(process.env.QQ_CHATBOT_NATIVE_CONFIG).catch(() => {
  // Native payloads can contain login material. Never echo them into host output.
  process.stderr.write('QQ_CHATBOT_NATIVE_START_FAILED\n');process.exit(5);
});
module.exports = {start};
