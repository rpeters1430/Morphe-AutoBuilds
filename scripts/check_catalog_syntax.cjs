// Check the real inline scripts too, without executing browser-only code.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../docs/index.html'), 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
for (const [index, match] of scripts.entries()) {
  new vm.Script(match[1], {filename: `docs/index.html script ${index + 1}`});
}
console.log(`Checked ${scripts.length} catalog scripts`);
