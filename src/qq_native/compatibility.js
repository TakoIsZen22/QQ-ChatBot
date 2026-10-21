'use strict';
const path = require('node:path');

function resolveCompatibility(catalog, policy, versions, root) {
  const profiles = catalog.schema === 'qq-chatbot.native-compat.v1'
    ? [{...catalog, adapter: 'embedded-qqnt-v1'}] : catalog.profiles;
  if (!Array.isArray(profiles)) throw new Error('invalid_compatibility_catalog');
  const matches = profiles.filter(x => x.version === policy.compatibility?.version);
  if (matches.length !== 1) throw new Error('unsupported_runtime');
  const selected = matches[0];
  // The C++ host ABI is checked in Python before loading QQNT.dll. Recheck the
  // actual runtime here before opening any gateway or invoking native login.
  if (selected.adapter !== 'embedded-qqnt-v1' || selected.node !== '24.11.1' ||
      selected.v8 !== '14.4.258.16-electron.0' || versions.node !== selected.node ||
      versions.v8 !== selected.v8 || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(selected.version)) throw new Error('unsupported_runtime');
  const client = path.resolve(root, '.runtime/qq-client/versions', selected.version);
  if (path.resolve(policy.client) !== client) throw new Error('invalid_runtime_path');
  // Never trust appid/qua or timing values supplied by a stale host-config.json.
  return {...selected, limits: catalog.limits};
}
module.exports = {resolveCompatibility};
