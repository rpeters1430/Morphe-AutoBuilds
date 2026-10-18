/* Shared catalog rendering helpers; also exercised by node --test. */
(function (root) {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const labels = {
    available: 'Download available', retained: 'Previous build retained', partial: 'Some architectures unavailable',
    not_built: 'Not built yet', unavailable: 'Temporarily unavailable', unknown: 'Availability unknown'
  };
  const android = {21: '5.0', 22: '5.1', 23: '6.0', 24: '7.0', 25: '7.1', 26: '8.0', 27: '8.1',
    28: '9', 29: '10', 30: '11', 31: '12', 32: '12L', 33: '13', 34: '14', 35: '15', 36: '16'};

  function compatibleWithArch(download, arch) {
    if (arch === 'all') return true;
    if (arch === 'universal') return download.arch === 'universal';
    const meta = download.metadata || {};
    if (meta.verified && Array.isArray(meta.native_abis)) {
      return meta.native_abis.length === 0 || meta.native_abis.includes(arch);
    }
    return download.arch === arch || download.arch === 'universal';
  }

  function renderMetadata(download) {
    const meta = download.metadata || {};
    if (!meta.verified) return '<p class="text-[11px] text-slate-500 mt-1">Compatibility not yet verified</p>';
    const minimum = android[meta.min_sdk] ? `Android ${android[meta.min_sdk]}+` : `Android API ${meta.min_sdk}+`;
    const abis = meta.native_abis?.length ? meta.native_abis.join(', ') : 'No native CPU restriction';
    return `<div class="text-[11px] text-slate-400 mt-1 break-words">
      <p>v${escape(meta.version_name)} · ${escape(minimum)} · ${escape(abis)}</p>
      <details class="mt-1"><summary class="cursor-pointer text-emerald-400">Signature verified · Details</summary>
        <p class="mt-1">Version code: ${escape(meta.version_code)}</p>
        <p>Package: ${escape(meta.package)}</p>
        <p>SHA-256: <code class="break-all select-all">${escape(meta.sha256)}</code></p>
        <p>Signing certificate: <code class="break-all select-all">${escape((meta.signer_sha256 || []).join(', '))}</code></p>
      </details></div>`;
  }

  function renderHealth(app) {
    const state = app.status || ((app.downloads || []).length ? 'available' : 'unknown');
    const color = state === 'available' ? 'text-emerald-400' : state === 'retained' || state === 'partial'
      ? 'text-amber-300' : 'text-slate-400';
    const rows = (app.health || []).map(item => {
      let link = '';
      try {
        const url = new URL(item.run_url);
        if (url.protocol === 'https:') link = `<a class="text-cyan-400 underline" target="_blank" rel="noopener" href="${escape(url.href)}">Build logs</a>`;
      } catch (_) { /* Older records have no run URL. */ }
      return `<div class="text-[11px] text-slate-400 mt-2 break-words">
        <p class="font-medium">${escape(item.arch)}</p>
        <p>Last success: ${escape(item.last_success_at || 'Not recorded')}</p>
        <p>Last attempt: ${escape(item.last_attempt_at || 'Not recorded')}</p>
        ${item.last_error ? `<p class="text-amber-300">${escape(item.last_error)}</p>` : ''}
        ${item.retry_after ? `<p>Retry backoff date: ${escape(item.retry_after)}. New inputs or a manual run can retry sooner.</p>` : ''}
        ${link}</div>`;
    }).join('');
    return `<div class="mb-3"><p class="text-xs font-medium ${color}">${escape(labels[state] || labels.unknown)}</p>
      ${rows ? `<details class="mt-1"><summary class="text-[11px] text-slate-400 cursor-pointer">Build history</summary>${rows}</details>` : ''}</div>`;
  }

  const api = {escape, labels, compatibleWithArch, renderMetadata, renderHealth};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.CatalogUI = api;
})(typeof window !== 'undefined' ? window : globalThis);
