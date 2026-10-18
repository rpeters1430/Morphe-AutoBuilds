const {test} = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../docs/catalog-ui.js');

test('actual native ABIs override universal filename when filtering', () => {
  const dl = {arch: 'universal', metadata: {verified: true, native_abis: ['armeabi-v7a']}};
  assert.equal(ui.compatibleWithArch(dl, 'arm64-v8a'), false);
  assert.equal(ui.compatibleWithArch(dl, 'armeabi-v7a'), true);
  assert.equal(ui.compatibleWithArch({arch: 'universal', metadata: {verified: true, native_abis: []}}, 'arm64-v8a'), true);
});

test('legacy metadata is clearly unknown and never labeled verified', () => {
  assert.match(ui.renderMetadata({metadata: {}}), /Compatibility not yet verified/);
  assert.doesNotMatch(ui.renderMetadata({metadata: {}}), /Signature verified/);
});

test('verified metadata renders real version, Android minimum and ABI coverage', () => {
  const html = ui.renderMetadata({metadata: {verified: true, version_name: '2.0', min_sdk: 26,
    version_code: '10', native_abis: ['arm64-v8a'], sha256: 'abc', signer_sha256: ['def']}});
  assert.match(html, /Android 8.0\+/);
  assert.match(html, /arm64-v8a/);
  assert.match(html, /Signature verified/);
  assert.match(html, /abc/);
});

test('health explains retained APK and escapes untrusted log text', () => {
  const html = ui.renderHealth({status: 'retained', health: [{arch: 'arm64-v8a', last_error: '<img src=x onerror=alert(1)>',
    last_attempt_at: '2026-10-18', last_success_at: '2026-10-17', retry_after: '2026-10-25', run_url: 'javascript:alert(1)'}]});
  assert.match(html, /Previous build retained/);
  assert.match(html, /Last success/);
  assert.match(html, /Last attempt/);
  assert.match(html, /2026-10-25/);
  assert.doesNotMatch(html, /<img|javascript:/);
});

test('missing download status messages distinguish not built and lookup failure', () => {
  assert.match(ui.renderHealth({status: 'not_built'}), /Not built yet/);
  assert.match(ui.renderHealth({status: 'unknown'}), /Availability unknown/);
});

test('real catalog template renders cards and filters verified ABI coverage', () => {
  const fs = require('node:fs');
  const vm = require('node:vm');
  const html = fs.readFileSync(require('node:path').join(__dirname, '../docs/index.html'), 'utf8');
  const elements = new Map();
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {value: 'all', classList: {add(){}, remove(){}, toggle(){}},
      addEventListener(){}, innerHTML: '', textContent: ''});
    return elements.get(id);
  }};
  const context = vm.createContext({document, CatalogUI: ui, lucide: {createIcons(){}},
    window: {addEventListener(){}}, URL, URLSearchParams, console});
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
  vm.runInContext(scripts.at(-1)[1], context);
  const app = {name: 'Example', slug: 'example', source: 'morphe', package: 'actual.package',
    category: 'Utilities', channel: 'stable', status: 'available', obtainium_config: null,
    downloads: [{arch: 'universal', size: '1 MB', download_url: 'https://example.com/app.apk',
      metadata: {verified: true, native_abis: ['armeabi-v7a'], min_sdk: 26, version_name: '1.0'}}]};
  vm.runInContext(`allApps = ${JSON.stringify([app])}; render()`, context);
  assert.match(elements.get('apps-grid').innerHTML, /Android 8.0\+/);
  assert.doesNotMatch(elements.get('apps-grid').innerHTML, /obtainium:\/\//);
  vm.runInContext("activeArch = 'arm64-v8a'; render()", context);
  assert.equal(elements.get('apps-grid').innerHTML, '');
});
