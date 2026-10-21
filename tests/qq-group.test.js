'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const {NativeDriver} = require('../src/qq_native/driver');
const {message} = require('../src/qq_native/protocol');
const {gateway} = require('../src/qq_native/gateway');
const policy = () => ({owner:'11111',bot:'22222',groups:['33333']});
const raw = (overrides={}) => ({msgId:'90071992547409931',msgTime:String(Math.floor(Date.now()/1000)),chatType:2,peerUid:'33333',senderUin:'44444',elements:[{elementType:1,textElement:{content:'@bot',atType:2,atNtUid:'u_bot'}}],...overrides});

test('native structured at resolves self UID, numeric QQ, and never guesses from visible text', () => {
  const p=policy();
  assert.equal(message(raw(),p,p.bot,'u_bot').message[0].data.qq,p.bot);
  const num=raw({elements:[{elementType:1,textElement:{content:'@bot',atType:2,atNtUin:'22222'}}]});
  assert.equal(message(num,p,p.bot).message[0].type,'at');
  const text=raw({elements:[{elementType:1,textElement:{content:'@22222'}}]});
  assert.equal(message(text,p,p.bot).message[0].type,'text');
  assert.equal(message(raw({senderUin:p.bot}),p,p.bot),null);
});

function setup(send) {
  const p=policy(),events=[];let listener;
  const driver=new NativeDriver(p,e=>events.push(e),()=>{});
  driver.login({uin:p.bot,uid:'u_bot'});
  driver.attach({getMsgService:()=>({addKernelMsgListener:x=>listener=x,sendMsg:send})});
  return {driver,receive:rows=>listener.onRecvMsg(rows),events};
}
const config=(groups=[{group_id:'33333',reply_enabled:true}],limit=5)=>({groups,group_per_minute:limit});
const params=(target='33333',parts=[{type:'text',data:{text:'hello'}}])=>({group_id:target,message:parts});

test('group sends require explicit reply permission plus an observed allowlisted group', async () => {
  const calls=[],{driver,receive}=setup(async (...a)=>{calls.push(a);return {result:0};});
  await assert.rejects(driver.action('send_group_msg',params()),/recipient_not_allowed/);
  await driver.action('configure_groups',config());
  await assert.rejects(driver.action('send_group_msg',params()),/group_must_message_first/);
  receive([raw()]);await driver.action('send_group_msg',params());
  assert.equal(calls[0][1].chatType,2);assert.equal(calls[0][1].peerUid,'33333');
  assert.equal(calls[0][2][0].textElement.atType,0);
  for(const parts of [[{type:'at',data:{qq:'all'}}],[{type:'image',data:{file:'x'}}]])
    await assert.rejects(driver.action('send_group_msg',params('33333',parts)),/text_only/);
  await assert.rejects(driver.action('send_group_msg',params('99999')),/recipient_not_allowed/);
  await driver.action('configure_groups',config([{group_id:'33333',reply_enabled:false}]));
  await assert.rejects(driver.action('send_group_msg',params()),/recipient_not_allowed/);
  assert.equal(calls.length,1);
});

test('hot group subscriptions filter incoming messages; invalid policies are atomic', async () => {
  const {driver,receive,events}=setup(async()=>({result:0}));
  await driver.action('configure_groups',config([{group_id:'55555',reply_enabled:false}]));
  receive([raw(),raw({peerUid:'55555'})]);
  assert.deepEqual(events.filter(e=>e.post_type==='message').map(e=>e.group_id),['55555']);
  for(const bad of [config([{group_id:'../x',reply_enabled:true}]),config([{group_id:'55555',reply_enabled:1}]),config(undefined,20),config(Array(13).fill({group_id:'55555',reply_enabled:false}))])
    await assert.rejects(driver.action('configure_groups',bad),/invalid_request/);
  assert.deepEqual(driver.policy.groups,['55555']);
});

test('native group hard quota includes ambiguous failures and survives policy sync', async () => {
  let count=0;const {driver,receive}=setup(async()=>{count++;return {result:1};});
  await driver.action('configure_groups',config());receive([raw()]);
  for(let i=0;i<5;i++) await assert.rejects(driver.action('send_group_msg',params()),/native_send_failed/);
  await driver.action('configure_groups',config());
  await assert.rejects(driver.action('send_group_msg',params()),/rate_limited/);
  assert.equal(count,5);
});

test('loopback gateway routes configure and group sends with no native method proxy', async () => {
  const calls=[],{driver,receive}=setup(async(...args)=>{calls.push(args);return {result:0};});
  const g=gateway(driver,{port:0});const addr=await g.listen();
  const post=(name,body)=>new Promise((resolve,reject)=>{
    const req=http.request({host:'127.0.0.1',port:addr.port,path:'/'+name,method:'POST',headers:{'Content-Type':'application/json','X-QQ-ChatBot':'1'}},res=>{
      let data='';res.on('data',c=>data+=c);res.on('end',()=>resolve(JSON.parse(data)));
    });req.on('error',reject);req.end(JSON.stringify(body));
  });
  try {
    assert.equal((await post('configure_groups',config())).data.configured,true);
    receive([raw()]);assert.equal((await post('send_group_msg',params())).status,'ok');
    assert.equal((await post('send_group_msg',params('99999'))).status,'failed');
    assert.equal(calls.length,1);
  } finally {await g.close();}
});
