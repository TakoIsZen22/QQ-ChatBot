'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {passwordLogin,officialUrl,authorized}=require('../src/qq_native/password_login');
const {gateway}=require('../src/qq_native/gateway');
const hash='a'.repeat(32);
function fixture(response){
  const calls=[],states=[];let online=false,clock=0;
  const service={async passwordLogin(value){calls.push(value);return typeof response==='function'?response(value):response}};
  const flow=passwordLogin(service,{bot:'12345',compatibility:{limits:{}}},{report:x=>states.push(x),online:()=>online,initializing:()=>false},()=>clock);
  return {flow,calls,states,online:()=>{online=true;flow.clear()},advance:()=>{clock+=6000}};
}
test('password accepted is not online; secret never enters public reports and clears on callback/cancel',async()=>{
  const f=fixture({result:'0'});
  assert.equal((await f.flow.action({action:'password',uin:'12345',password_md5:hash})).phase,'password_accepted');
  assert.equal(f.calls[0].step,0);assert.equal(f.calls[0].passwordMd5,hash);
  assert.ok(f.states.every(x=>!x.online));assert.ok(!JSON.stringify(f.states).includes(hash));
  f.online();assert.equal(f.flow.waiting(),false);
  await assert.rejects(f.flow.action({action:'password',uin:'12345',password_md5:hash}),/already_logged_in/);
});
test('captcha and device continuation retain challenge only in memory, use correct QQNT stages',async()=>{
  const f=fixture(({step})=>step===0?{result:'140022008',loginErrorInfo:{proofWaterUrl:'https://ssl.captcha.qq.com/test?aid=1&sid=private-sid'}}:
    step===1?{result:'140022010',loginErrorInfo:{jumpUrl:'https://accounts.qq.com/verify',newDevicePullQrCodeSig:'private-sig'}}:{result:'0'});
  const result=await f.flow.action({action:'password',uin:'12345',password_md5:hash});assert.equal(result.phase,'password_captcha');
  assert.equal((await f.flow.action({action:'challenge'})).kind,'captcha');
  await assert.rejects(f.flow.action({action:'continue',challenge_id:'old-challenge',ticket:'x',randstr:'y'}),/challenge_unavailable/);
  await f.flow.action({action:'continue',challenge_id:(await f.flow.action({action:'challenge'})).challenge_id,ticket:'real-user-ticket',randstr:'random'});
  assert.equal(f.calls[1].step,1);assert.equal(Buffer.from(f.calls[1].proofWaterSid).toString(),'private-sid');
  await f.flow.action({action:'continue',challenge_id:(await f.flow.action({action:'challenge'})).challenge_id});assert.equal(f.calls[2].step,2);
  assert.equal(Buffer.from(f.calls[2].newDeviceLoginSig).toString(),'private-sig');
  assert.ok(!JSON.stringify(f.states).includes('private-'));
  f.flow.clear();await assert.rejects(f.flow.action({action:'challenge'}),/challenge_unavailable/);
});
test('untrusted challenge/native exception is sanitized; account guard and throttle cannot be bypassed by QR cancel',async()=>{
  const f=fixture({result:'140022008',loginErrorInfo:{proofWaterUrl:'http://evil.test/?secret=1'}});
  await assert.rejects(f.flow.action({action:'password',uin:'99999',password_md5:hash}),/invalid_request/);assert.equal(f.calls.length,0);
  assert.equal((await f.flow.action({action:'password',uin:'12345',password_md5:hash})).phase,'password_failed');
  await f.flow.action({action:'cancel'});
  await assert.rejects(f.flow.action({action:'password',uin:'12345',password_md5:hash}),/login_rate_limited/);
  for(let i=0;i<4;i++){f.advance();await f.flow.action({action:'password',uin:'12345',password_md5:hash})}
  f.advance();await assert.rejects(f.flow.action({action:'password',uin:'12345',password_md5:hash}),/login_rate_limited/);
  for(const url of ['https://qq.com.evil.test/a','http://qq.com/a','https://user@qq.com/a','https://qq.com:123/a','javascript:alert(1)'])assert.equal(officialUrl(url),'');
  assert.ok(!authorized('short','short'));assert.ok(authorized('a'.repeat(64),'a'.repeat(64)));
});
test('local password IPC needs per-run authorization and never exposes native errors',async()=>{
  let calls=0;const token='b'.repeat(64);
  const bridge=gateway({online:false}, {port:0,login_token:token},async data=>{calls++;if(data.action==='bad')throw Error('secret-native-error');return {phase:'password_accepted'}});
  const addr=await bridge.listen();const url=`http://127.0.0.1:${addr.port}/login_control`;
  try{
    const headers={'Content-Type':'application/json','X-QQ-ChatBot':'1'};
    assert.equal((await fetch(url,{method:'POST',headers,body:'{}'})).status,403);assert.equal(calls,0);
    headers['X-QQ-Login']=token;
    assert.equal((await (await fetch(url,{method:'POST',headers,body:'{}'})).json()).data.phase,'password_accepted');
    const error=await (await fetch(url,{method:'POST',headers,body:'{"action":"bad"}'})).json();
    assert.equal(error.message,'native_error');assert.ok(!JSON.stringify(error).includes('secret'));
    assert.equal((await fetch(url,{method:'POST',headers:{...headers,Origin:'https://example.com'},body:'{}'})).status,403);
  }finally{await bridge.close()}
});

test('unresponsive native login expires and requires manual restart, never silently overlaps calls',async()=>{
  let calls=0;const states=[];
  const f=passwordLogin({passwordLogin(){calls++;return new Promise(()=>{})}},
    {bot:'12345',compatibility:{limits:{password_timeout_ms:20}}},
    {report:x=>states.push(x),online:()=>false,initializing:()=>false});
  await f.action({action:'password',uin:'12345',password_md5:hash});
  assert.equal(f.waiting(),false);assert.equal(states.at(-1).phase,'password_expired');
  await assert.rejects(f.action({action:'password',uin:'12345',password_md5:hash}),/login_restart_required/);
  assert.equal(calls,1);
});

test('password native success attaches the validated account; stale QR events cannot replace password state',async()=>{
  const {initialize}=require('../src/qq_native/session'),{NativeDriver}=require('../src/qq_native/driver');
  const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'qq-password-session-'));let listener;
  const states=[];
  try{
    const policy={bot:'12345',owner:'54321',groups:[],directory,compatibility:{version:'fixture',appid:'1',qua:'fixture'}};
    const login={initConfig(){},connect(){},addKernelLoginListener(value){listener=value},
      getMachineGuid(){return '0123456789abcdef0123456789abcdef'},passwordLogin:async()=>({result:'0'})};
    const nativeSession={getMsgService:()=>({addKernelMsgListener(){}}),init(c,n,a,ready){ready.onOpentelemetryInit({is_init:true})}};
    const api={NodeIQQNTWrapperEngine:{get:()=>({initWithDeskTopConfig(){}})},NodeIKernelLoginService:{get:()=>login},
      NodeIQQNTStartupSessionWrapper:{create:()=>({start(){}})},NodeIQQNTWrapperSession:{getNTWrapperSession:()=>nativeSession}};
    const driver=new NativeDriver(policy,()=>{},s=>states.push(s));
    const session=initialize(api,policy,driver,s=>states.push(s));
    await session.password({action:'password',uin:policy.bot,password_md5:hash});
    assert.equal(states.at(-1).phase,'password_accepted');assert.equal(driver.online,false);
    listener.onQRCodeSessionFailed(1,3);listener.onQRCodeSessionUserScaned();listener.onLoginDisConnected();
    assert.equal(states.at(-1).phase,'password_accepted');
    listener.onQRCodeLoginSucceed({uin:policy.bot,uid:'u_fixture'});
    assert.equal((await driver.action('get_status')).online,true);assert.equal(states.at(-1).phase,'ready');
    session.stop();
  }finally{fs.rmSync(directory,{recursive:true,force:true})}
});
