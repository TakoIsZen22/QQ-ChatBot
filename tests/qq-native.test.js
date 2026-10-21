'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const {message, textRequest} = require('../src/qq_native/protocol');
const {NativeDriver} = require('../src/qq_native/driver');
const {gateway} = require('../src/qq_native/gateway');
const fs = require('node:fs');
const vm = require('node:vm');

const policy = {owner: '11111', bot: '22222', groups: ['33333']};
function raw(overrides = {}) {return {msgId: '90071992547409931', msgTime: '1700000000', chatType: 1, senderUin: '11111', senderUid: 'u_owner', elements: [{elementType: 1, textElement: {content: '你好'}}], ...overrides};}
test('message IDs remain exact and only owner / allowed groups are admitted', () => {
  assert.equal(message(raw(), policy, policy.bot).message_id, '90071992547409931');
  assert.equal(message(raw({senderUin: '44444'}), policy, policy.bot), null);
  assert.equal(message(raw({senderUin: policy.bot}), policy, policy.bot), null);
  assert.equal(message(raw({chatType: 2, peerUid: '99999'}), policy, policy.bot), null);
  assert.equal(message(raw({chatType: 2, peerUid: '33333'}), policy, policy.bot).group_id, '33333');
});
test('media does not disclose local paths or credentials in URLs', () => {
  const event = message(raw({elements: [{elementType: 2, picElement: {sourcePath: 'private-path', originImageUrl: 'https://secret@host.invalid/image'}}]}), policy, policy.bot);
  assert.ok(!JSON.stringify(event).includes('private-path'));
  assert.ok(!JSON.stringify(event).includes('secret'));
});
test('send cannot target a group, stranger, media or at-all', () => {
  for (const params of [{user_id: '99999', message: []}, {user_id: policy.owner, group_id: '33333', message: []}, {user_id: policy.owner, message: [{type: 'at', data: {qq: 'all'}}]}]) assert.throws(() => textRequest(params, policy.owner));
});
test('native sends use only an observed owner UID and consume the hard quota on failure', async () => {
  let listener, calls = 0;
  const driver = new NativeDriver(policy, () => {}, () => {});
  driver.login({uin: policy.bot});
  driver.attach({getMsgService: () => ({addKernelMsgListener: value => {listener = value;}, sendMsg: async (...args) => {calls++; assert.equal(args[1].peerUid, 'u_owner'); return {result: 0};}})});
  const params = {user_id: policy.owner, message: [{type: 'text', data: {text: 'hello'}}]};
  await assert.rejects(driver.action('send_private_msg', params), /owner_must_message_first/);
  listener.onRecvMsg([raw()]);
  for (let i = 0; i < 20; i++) await driver.action('send_private_msg', params);
  await assert.rejects(driver.action('send_private_msg', params), /rate_limited/);
  assert.equal(calls, 20);
  await assert.rejects(driver.action('send_group_msg', {}), /recipient_not_allowed/);
  for (const name of ['set_friend_add_request','get_credentials','get_friend_msg_history']) await assert.rejects(driver.action(name, {}), /unsupported_action/);
  driver.offline();
  assert.equal((await driver.action('get_status')).online, false);
});
test('wrong account fails closed', async () => {
  const driver = new NativeDriver(policy, () => {}, () => {});
  driver.login({uin: '99999'});
  await assert.rejects(driver.action('get_login_info'), /not_logged_in/);
});

test('login ready, offline and same-session recovery publish state immediately', () => {
  const events=[];const states=[];const service={addKernelMsgListener(){}};
  const session={getMsgService:()=>service};
  const driver=new NativeDriver(policy,e=>events.push(e),s=>states.push(s));
  driver.login({uin:policy.bot});driver.attach(session);
  assert.equal(events.at(-1).status.online,true);assert.equal(states.at(-1).phase,'ready');
  driver.offline();assert.equal(events.at(-1).status.online,false);
  driver.login({uin:policy.bot});driver.attach(session);
  assert.equal(events.at(-1).status.online,true);
  driver.login({uin:'99999'});assert.equal(events.at(-1).status.online,false);
});
test('bootstrap observes the official session without initializing a second session', async () => {
  let loginListener, messageListener, originalReady = 0, initialized = 0, created = 0;
  const files = new Map();
  const session = {init(...args) {initialized++; args[3].onOpentelemetryInit({is_init:true});}, getMsgService() {return {addKernelMsgListener(value) {messageListener = value;}};}};
  const api = {NodeIQQNTWrapperSession:{create() {created++;return session;}}, NodeIKernelLoginService:{get() {return {addKernelLoginListener(value) {loginListener = value;}};}}};
  const mockProcess = {dlopen(module) {module.exports = api;return 'original_result';}};
  const context = {module:{exports:{}},process:mockProcess,Buffer,require(name) {
    if (name === 'node:fs') return {mkdirSync(){},writeFileSync(file, data){files.set(file,data);},renameSync(from,to){files.set(to,files.get(from));}};
    if (name === './gateway') return {gateway(){return {listen:async()=>{},emit(){}};}};
    return require(name.startsWith('./') ? '../src/qq_native/'+name.slice(2) : name);
  }};
  vm.runInNewContext(fs.readFileSync(require.resolve('../src/qq_native/bootstrap'),'utf8'), context);
  const runtime = context.module.exports.install({...policy, port:3002, directory:require('node:path').resolve('fixture')});
  const module = {};
  assert.equal(mockProcess.dlopen(module,'wrapper.node'), 'original_result');
  const login = module.exports.NodeIKernelLoginService.get();
  const wrapped = module.exports.NodeIQQNTWrapperSession.create();
  wrapped.init({}, {}, {}, {onOpentelemetryInit(){originalReady++;}});
  loginListener.onQRCodeLoginSucceed({uin:policy.bot});
  assert.equal(runtime.driver.online, true);
  assert.equal(typeof messageListener.onRecvMsg,'function');
  assert.equal(created,1);assert.equal(initialized,1);assert.equal(originalReady,1);
  loginListener.onLoginDisConnected();
  assert.equal(runtime.driver.online,false);
  assert.equal(typeof login.addKernelLoginListener,'function');
});

function request(port, pathname, body = '{}', headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({hostname: '127.0.0.1', port, path: pathname, method: 'POST', headers: {'Content-Type':'application/json','X-QQ-ChatBot':'1', ...headers}}, res => {
      const chunks = [];res.on('data', chunk => chunks.push(chunk));res.on('end', () => resolve({status: res.statusCode, body: Buffer.concat(chunks).toString()}));
    });
    req.on('error', reject);req.end(body);
  });
}
test('real loopback gateway rejects origin / host / header / unknown actions and opaque errors', async t => {
  const bridge = gateway({online: false, action: async name => {if (name === 'get_status') return {online:false};throw new Error('private-native-error');}}, {port:0});
  t.after(() => bridge.close());
  const {port} = await bridge.listen();
  assert.equal((await request(port, '/get_status')).status, 200);
  for (const headers of [{'Origin':'https://host.invalid'}, {'Host':'evil.invalid'}, {'X-QQ-ChatBot':''}]) assert.equal((await request(port, '/get_status', '{}', headers)).status, 403);
  assert.equal((await request(port, '/set_friend_add_request')).status, 404);
  assert.equal((await request(port, '/get_status', 'x'.repeat(65537))).status, 413);
  const response = await request(port, '/get_login_info');
  assert.ok(!response.body.includes('private-native-error'));
  assert.equal(JSON.parse(response.body).message, 'native_error');
});
test('real event stream carries heartbeats and observed events', async t => {
  const bridge = gateway({online: false}, {port:0});
  t.after(() => bridge.close());
  const {port} = await bridge.listen();
  const events = await new Promise((resolve, reject) => {
    const req = http.get({hostname:'127.0.0.1',port,path:'/events',headers:{'X-QQ-ChatBot':'1'}}, res => {
      let data = '';
      res.on('data', chunk => {
        data += chunk.toString();
        const lines = data.trim().split('\n');
        if (lines.length === 1) bridge.emit({post_type:'message',message_id:'fixture'});
        if (lines.length >= 2) {res.destroy();resolve(lines.map(JSON.parse));}
      });
    });req.on('error', reject);
  });
  assert.equal(events[0].meta_event_type, 'heartbeat');
  assert.equal(events[1].message_id, 'fixture');
});


test('offline callbacks and account switches cannot leak late messages', async () => {
  let listener;const events=[];
  const service={addKernelMsgListener(x){listener=x;}};
  const session={getMsgService(){return service;}};
  const driver=new NativeDriver(policy,e=>events.push(e),()=>{});
  driver.login({uin:policy.bot});driver.attach(session);listener.onRecvMsg([raw()]);
  assert.equal(events.filter(x=>x.post_type==='message').length,1);
  driver.offline();listener.onRecvMsg([raw()]);
  assert.equal((await driver.action('get_status')).good,false);
  assert.equal(events.filter(x=>x.post_type==='message').length,1);
  driver.login({uin:policy.bot});driver.attach(session);listener.onRecvMsg([raw()]);
  assert.equal(events.filter(x=>x.post_type==='message').length,2);
  driver.login({uin:'99999'});listener.onRecvMsg([raw()]);
  assert.equal(events.filter(x=>x.post_type==='message').length,2);
});

test('own session writes isolated QR only and rejects wrong or late account login', () => {
  const os=require('node:os'),path=require('node:path');
  const {initialize}=require('../src/qq_native/session');
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qq-session-test-'));
  try {
    let listener,created=0,requested=0;const states=[];
    const login={initConfig(c){assert.ok(c.commonPath.startsWith(dir));},addKernelLoginListener(x){listener=x;},connect(){listener.onLoginConnected();},getQRCodePicture(){requested++;}};
    const api={NodeIQQNTWrapperEngine:{get(){return {initWithDeskTopConfig(c){assert.ok(c.global_path_config.desktopGlobalPath.startsWith(dir));}};}},NodeIKernelLoginService:{get(){return login;}},NodeIQQNTStartupSessionWrapper:{create(){created++;throw Error('unexpected');}}};
    const p={...policy,directory:dir,compatibility:{version:'fixture',appid:'1',qua:'fixture'}};
    const driver=new NativeDriver(p,()=>{},x=>states.push(x));
    const session=initialize(api,p,driver,x=>states.push(x));
    assert.equal(requested,1);
    listener.onQRCodeGetPicture({pngBase64QrcodeData:Buffer.from('invalid').toString('base64')});
    assert.ok(!fs.existsSync(path.join(dir,'qrcode.png')));
    const png=Buffer.from([137,80,78,71,13,10,26,10]);
    listener.onQRCodeGetPicture({pngBase64QrcodeData:png.toString('base64')});
    assert.deepEqual(fs.readFileSync(path.join(dir,'qrcode.png')),png);
    listener.onQRCodeLoginSucceed({uin:'99999',uid:'u_stranger'});
    assert.equal(created,0);assert.equal(driver.online,false);
    session.stop();listener.onQRCodeLoginSucceed({uin:p.bot,uid:'u_bot'});
    assert.equal(created,0);assert.equal(driver.online,false);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});


test('QR transport closure and initial MSF disconnect do not invalidate the new account session', async () => {
  const {initialize}=require('../src/qq_native/session'),os=require('node:os'),path=require('node:path');
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qq-transition-test-'));let listener,network;
  try {
    const service={addKernelMsgListener(){}};
    const nativeSession={getMsgService(){return service;},init(c,n,a,ready){
      assert.ok(c.desktopPathConfig.account_path.startsWith(dir));network=n;
      listener.onLoginDisConnected();n.onMSFStatusChange(1,0);ready.onOpentelemetryInit({is_init:true});
    }};
    const login={initConfig(){},getMachineGuid(){return '0123456789abcdef0123456789abcdef';},addKernelLoginListener(x){listener=x;},connect(){},getQRCodePicture(){}};
    const api={NodeIQQNTWrapperEngine:{get(){return {initWithDeskTopConfig(){}};}},NodeIKernelLoginService:{get(){return login;}},NodeIQQNTStartupSessionWrapper:{create(){return {start(){}};}},NodeIQQNTWrapperSession:{getNTWrapperSession(){return nativeSession;}}};
    const p={...policy,directory:dir,compatibility:{version:'fixture',appid:'1',qua:'fixture'}};
    const driver=new NativeDriver(p,()=>{},()=>{});initialize(api,p,driver,()=>{});
    listener.onQRCodeLoginSucceed({uin:p.bot,uid:'u_bot'});
    assert.deepEqual(await driver.action('get_status'),{online:true,good:true});
    network.onMSFStatusChange(1,0);assert.deepEqual(await driver.action('get_status'),{online:false,good:false});
    network.onMSFStatusChange(2,0);assert.deepEqual(await driver.action('get_status'),{online:true,good:true});
    listener.onLogoutSucceed();network.onMSFStatusChange(2,0);assert.equal(driver.online,false);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
