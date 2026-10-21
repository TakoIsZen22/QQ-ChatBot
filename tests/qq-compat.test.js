'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {resolveCompatibility} = require('../src/qq_native/compatibility');
const root = path.resolve('.');
const a = {version:'fixture-a',adapter:'embedded-qqnt-v1',node:'24.11.1',v8:'14.4.258.16-electron.0',appid:'12345',qua:'trusted'};
const catalog = {schema:'qq-chatbot.native-compat.v2',preferred:a.version,profiles:[a,{...a,version:'fixture-b'}],limits:{control_poll_ms:250}};
const versions = {node:a.node,v8:a.v8};
const policy = version => ({compatibility:{version,appid:'untrusted'},client:path.join(root,'.runtime/qq-client/versions',version)});
test('selects the requested profile from trusted catalog, ignoring stale policy parameters', () => {
  const selected = resolveCompatibility(catalog,policy('fixture-b'),versions,root);
  assert.equal(selected.version,'fixture-b');assert.equal(selected.appid,'12345');assert.equal(selected.qua,'trusted');
  assert.equal(selected.limits.control_poll_ms,250);
});
test('rejects unknown versions, ABI drift and paths outside the dedicated version', () => {
  assert.throws(() => resolveCompatibility(catalog,policy('unknown'),versions,root));
  assert.throws(() => resolveCompatibility(catalog,policy('fixture-a'),{...versions,node:'25'},root));
  assert.throws(() => resolveCompatibility(catalog,{...policy('fixture-a'),client:root},versions,root));
  assert.throws(() => resolveCompatibility({...catalog,profiles:[{...a,adapter:'unknown'}]},policy('fixture-a'),versions,root));
});
test('existing v1 catalogs remain readable during upgrade', () => {
  const old={...a,schema:'qq-chatbot.native-compat.v1',limits:catalog.limits};delete old.adapter;
  assert.equal(resolveCompatibility(old,policy('fixture-a'),versions,root).appid,'12345');
});
