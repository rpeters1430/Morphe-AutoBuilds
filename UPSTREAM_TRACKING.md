# Upstream Synchronization & Porting Tracker

This document tracks commits from the original upstream repository ([`RookieEnough/Morphe-AutoBuilds`](https://github.com/RookieEnough/Morphe-AutoBuilds)) and records what has been ported, cherry-picked, or intentionally skipped in this repository ([`rpeters1430/Morphe-AutoBuilds`](https://github.com/rpeters1430/Morphe-AutoBuilds)).

---

## 🧭 Repository Architecture Differences

Our repository maintains several distinct subsystems that are not present upstream:
1. **Interactive Maintainer Suite (`morphe.py`)**: Terminal TUI for app management, patch editing, CI dispatching, and health checking.
2. **Web App Catalog & Obtainium Integration (`docs/`)**: Mobile-friendly web catalog with QR code support and deterministic Obtainium regex filtering (`^<app>-(arm64-v8a|armeabi-v7a|universal)-.*\.apk$`).
3. **Automated Unit Testing (`tests/`)**: Regression coverage across archive validation, download scrapers, signature preservation, and patch pipelines.
4. **Native morphe-cli Bundle Merging**: Automatic bundle passing to `morphe-cli` with ABI library stripping on output APKs, preserving stock signature metadata until after patching.
5. **Release Hosting Target**: We publish to **GitHub Releases**, whereas upstream migrated releases to Codeberg and subsequently GitLab.

Because of these architectural divergences, upstream commits are **reviewed, curated, and cherry-picked/adapted** rather than merged directly.

---

## 📜 Upstream Commits Ledger

| Upstream Commit | Date | Summary | Category | Status in Our Repo | Notes / Rationale |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `c0856e2` | 2026-10-13 | Detect APKPure XAPK and archive download links | Scrapers | ✅ Adapted | Added direct APK/XAPK discovery from download anchors, `data-href`, and embedded URLs; only accepts HTTPS `d.apkpure.com/b/{APK,XAPK}/` endpoints and adds regression tests. |
| `37ab7e7` | 2026-10-13 | Refresh APKMirror Gboard config | App Config | ✅ Ported | Switched to the APK/nodpi listing and removed the stale version pin and beta filter. |
| `b1539df` | 2026-10-13 | Refresh APKMirror Google Maps config | App Config | ✅ Ported | Switched from the arm64 bundle listing to the universal APK/nodpi listing. |
| `461a086` / `77afad5` | 2026-10-13 | Add HushPinterest patch source and switch Pinterest | Sources / App | ✅ Ported | Added `sources/hushpinterest.json`, switched Pinterest from `adobo`, and moved the existing ad-removal override to HushPinterest's `Hide ads` patch. APKPure app config already existed. |
| `c0a7dc1` | 2026-10-13 | Remove duplicate Gboard entry | Config | ⏭️ Not needed | Our `patch-config.json` already contains a single Gboard entry (`morning-entree`); upstream's extra `3r01` entry is not present. |
| `3dcc9bb` | 2026-10-11 | Add new mods and fixed Gboard apk version (PR #147) | Apps / Configs | ✅ Ported | Added `google-maps` (bearinmindcat), `3r01` (Gboard), and Gboard exclusion fixes. |
| `7612833` | 2026-10-10 | Add secret GitLab token validation to release workflow | CI / GitLab | ⏸️ Skipped | Specific to upstream's GitLab release publishing. We publish to GitHub Releases. |
| `3d5d1ec` | 2026-10-10 | Merge patch-config | Config | ✅ Ported | Sources updated for messenger (`hushmessenger`), letterboxd (`kim20598`), and niagara (`d0nj`). Preserved our disabled app entries (`"enabled": false`) instead of hard deletion. |
| `8cb8a7d` .. `908df38` | 2026-10-10 | GitLab asset-link and move_tag wipe fixes | GitLab | ⏸️ Skipped | Upstream GitLab API workarounds. |
| `c0b6585` .. `0531bc1` | 2026-10-09 | Rebuild GitLab links workflow & package file listing | GitLab | ⏸️ Skipped | Upstream GitLab API workarounds. |
| `f272f3b` | 2026-10-09 | Fix #145 guard false positive on CLI-truncated versions | Build Guard | ✅ Ported | Strip trailing `.` from truncated CLI versions in `Filtering patches for` validation. |
| `e8a18dd` / `6c01db7` | 2026-10-08 | Fail the build when no patches apply (PR #145) | Build Guard | ✅ Ported | Integrated version mismatch rejection into `_reject_empty_patch_run`. |
| `3fa7c35` .. `32b469b` | 2026-10-08 | GitLab release links / package registry fixes | GitLab | ⏸️ Skipped | Upstream GitLab hosting logic. |
| `2b8d14d` | 2026-10-07 | Fix Gboard: strip variant from version, exclude beta in Aptoide | Scrapers | ✅ Ported | Added `extract_base_version()` in `apkmirror.py` and variant stripping in `aptoide.py`. |
| `d3aa740` | 2026-10-07 | Support `exclude_variant` in apkmirror downloader | Scrapers | ✅ Ported | Added `exclude_variant` check to `_scrape_release_url_from_soup`. |
| `8559c38` | 2026-10-07 | Fix Gboard: exclude beta variant (patches require release) | App Config | ✅ Ported | Added `"exclude_variant": "beta"` to `apps/apkmirror/gboard.json`. |
| `e8cc9a8` | 2026-10-07 | Remove hardcoded versions from apkmirror configs | App Config | ✅ Ported | Empty version strings for dynamic version detection (`crunchyroll`, `nova`, `wps-office`). |
| `833b4f2` | 2026-10-07 | Fix APKMirror slugs (crunchyroll, nova, wps-office) | App Config | ✅ Ported | Fixed APKMirror slugs; kept disabled apps configured rather than deleting. |
| `ca822a3` / `dd165f3` | 2026-10-07 | `--continue-on-error` patcher experiment and revert | Patching | ⏸️ Skipped | Upstream reverted this immediately. Our repo already handles per-app build flags in `build_config.py`. |
| `5c2a960` | 2026-10-07 | Disable failing patches and fix APKPure API URL matching | Patches / Scrapers | ✅ Ported | Added patch exclusions for viber, proton-mail, lingory. |
| `be70e04` | 2026-10-07 | Adapt download validation: zip check only, no signature pre-check | Validation | 🔄 Replaced | Upstream deleted signature checks. We implemented `ensure_usable_android_archive` to verify Android manifests/DEX while preserving stock signatures until patching. |
| `90a98e8` / `89a22b1` | 2026-10-07 | Fix XAPK handling: passthrough to APKEditor instead of extracting | Bundles | 🔄 Replaced | Our repo handles native morphe-cli merging with fallback to APKEditor. |
| `efde58e` | 2026-10-07 | APKPure: use official API first, keep FlareSolverr fallback | Scrapers | ✅ Ported | API first with ABI prioritization (`_abi_rank`) and FlareSolverr + regex URL match fallback. |
| `34e1a7d` | 2026-10-07 | Add APKFab mirror for exact-version downloads | Scrapers | ✅ Ported | Ported previously in commit `d9d2f6e`. |
| `e693071` | 2026-10-07 | Aptoide: fix website scrape for CI (slug overrides + FlareSolverr) | Scrapers | ✅ Ported | Integrated website scrape, slug overrides (`mirinae`, `sofascore`, `snorelab`), and FlareSolverr fallback. |
| `c9fd5f6` | 2026-10-07 | Fix Aptoide stale API and Uptodown Gboard slug | Scrapers | ✅ Ported | Added Uptodown slug override `gboard-go` and website version extraction. |
| `91c7702` | 2026-10-07 | Use Hush for messenger, Kim20598 for letterboxd | Sources | ✅ Ported | Added `hushmessenger.json` and `kim20598.json`. |
| `41fc4c8` | 2026-10-07 | Move messenger, strava, pixiv, letterboxd off De-Vanced | Sources | ✅ Ported | Re-pointed patch sources off dead De-Vanced repository. |
| `24f7f44` / `e0902c3` | 2026-10-07 | FlareSolverr Docker service & client for Cloudflare bypass | CI / Scrapers | ✅ Ported | Ported previously in commit `d9d2f6e`. |
| `059edca` | 2026-10-07 | Integrate FlareSolverr into APKCombo downloader | Scrapers | ✅ Ported | Added `flaresolverr.get_with_bypass` in `_page()`. |
| `6444403` | 2026-10-07 | Integrate FlareSolverr into Uptodown downloader | Scrapers | ✅ Ported | Added FlareSolverr fallback when Cloudflare challenge is detected in `_get()`. |
| `636763c` | 2026-10-07 | Improve APKPure download link extraction | Scrapers | ✅ Ported | Added direct regex download link check on APKPure download page. |
| `001862a` / `cefcb36` | 2026-10-06 | Add canh0chua patch source and Viber to build list | Sources / App | ✅ Ported | Added `sources/canh0chua.json`, `patches/viber-canh0chua.txt`, and `apps/apkmirror/viber.json`. |
| `e74560d` / `4f833db` | 2026-10-06 | Port release hosting from GitHub -> Codeberg -> GitLab | Releases | ⏸️ Skipped | Our repo remains on GitHub Releases with Pages portal and Obtainium support. |
| `11dc19c` | 2026-10-06 | Switch Niagara to d0nj patches | Sources | ✅ Ported | Added `sources/d0nj.json` and updated `patch-config.json`. |
| `1596e28` .. `eba1f4b` | 2026-10-07 | Update APKMirror JSON configurations | App Configs | ✅ Ported | Updated slugs/configs for `rar`, `spotify`, `strava`, `tumblr`, `viber`, `proton-vpn`, `smart_launcher`, `sofascore`, `soundcloud`. |
| — | 2026-10-11 | Add AiScore with Doom (`rushiranpise`) patches | Apps / Configs | ✅ Added | Added `apps/apkpure/aiscore.json` and enabled in `patch-config.json` and `arch-config.json`. |

---

## 🛠️ How to Check & Port Future Upstream Commits

To inspect new commits from the upstream repository:

```bash
# 1. Fetch latest changes from upstream
git fetch upstream

# 2. View new upstream commits not yet in our branch
git log HEAD..upstream/main --oneline

# 3. Inspect a specific commit with diff
git show <commit-sha>

# 4. Compare a specific file between our repo and upstream
git diff HEAD..upstream/main -- src/apkmirror.py

# 5. Run local test suite and config validator before committing
python -m unittest discover tests
python scripts/validate_config.py
```
