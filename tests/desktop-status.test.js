'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function fixture(request,runtime){
  const window={pywebview:{api:{request,runtime}},addEventListener(){}};
  // Exercise the real poll coordinator with renderers stubbed, not a second coordinator.
  const source=fs.readFileSync(require.resolve('../src/channel/ui/desktop/desktop.js'),'utf8')
    .replace('window.DFY={', 'renderStatus=()=>{};renderChat=()=>{};refreshData=async()=>{};window.qqLabel=qqLabel;window.DFY={');
  vm.runInNewContext(source,{window,document:{documentElement:{dataset:{desktopHost:'native'}},querySelector(){return {open:false}}},location:{hash:''},setTimeout(){}});
  window.DFY.state.cfg={qq:{enabled:true}};
  return window;
}
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};

test('status updates while transcript and usage requests are stalled; no duplicate slow requests',async()=>{
  const chat=deferred(),usage=deferred();let status={qq_enabled:true,qq_connected:false,qq_online:false},reads=0,chats=0,runtimes=0;
  const w=fixture(async path=>{if(path==='status'){reads++;return status}if(path==='chat'){chats++;return chat.promise}throw Error(path)},()=>{runtimes++;return usage.promise});
  await w.DFY.poll();assert.equal(w.qqLabel(),'QQ 未连接');
  w.DFY.updateQQSession({phase:'ready'});assert.equal(w.qqLabel(),'QQ 已登录 · 通道连接中');
  status={qq_enabled:true,qq_connected:true,qq_online:true};
  await w.DFY.poll();assert.equal(w.qqLabel(),'QQ 已连接');
  status={qq_enabled:true,qq_connected:false,qq_online:false};w.DFY.updateQQSession({phase:'offline'});
  await w.DFY.poll();assert.equal(w.qqLabel(),'QQ 未连接');
  assert.equal(reads,3);assert.equal(chats,1);assert.equal(runtimes,1);
  chat.resolve([]);usage.resolve({});
});

test('overlapping status reads share a request and failures show unknown rather than stale online',async()=>{
  const pending=deferred();let calls=0,failed=false;
  const w=fixture(path=>{if(path==='status'){calls++;return failed?Promise.reject(Error('offline')):pending.promise}return Promise.resolve([])},async()=>({}));
  const one=w.DFY.poll(),two=w.DFY.poll();assert.equal(calls,1);
  pending.resolve({qq_enabled:true,qq_connected:true,qq_online:true});await Promise.all([one,two]);
  assert.equal(w.qqLabel(),'QQ 已连接');failed=true;await w.DFY.poll();assert.equal(w.qqLabel(),'QQ 状态待确认');
});
