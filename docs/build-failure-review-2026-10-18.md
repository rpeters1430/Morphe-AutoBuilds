# Full-build failure review — October 18, 2026

Reviewed [run 39146864070](https://github.com/rpeters1430/Morphe-AutoBuilds/actions/runs/39146864070), started at 16:50 UTC on commit `e2caf606`. This was a manually triggered run of the automatic build workflow: 105 app jobs, 86 successful and 19 failed. The release job succeeded and published successful outputs.

## Findings and changes

| App | Evidence from failed build | Response |
| --- | --- | --- |
| Proton VPN | Patched successfully, then verification rejected extra `armeabi`, `mips`, `mips64` directories | Strip every native ABI outside the configured ARM targets before final verification. |
| Proton Mail | Same legacy-directory verification failure | Same cleanup correction. |
| Podcast Addict | Patched successfully; extra `armeabi` remained | Same cleanup correction. |
| CamScanner | Downloaded XAPK contained only `armeabi` | Reject incompatible archives before choosing a provider; try another source instead of aborting that app immediately. Remains dependent on a modern ARM build being available. |
| Threads | APKFab served an x86_64-only XAPK | Prefer ARM variants in APKFab listings; validate actual nested APK libraries before accepting the download. |
| MacroDroid | APKPure selected x86_64-only input | Filter incompatible API entries and try other providers before patching. |
| Pinterest | APKPure's latest entry was ChromeOS stub `2000000000.0.0-CrOS`; zero patches applied | Exclude non-phone channels from latest-version selection. Exact supported version is still required. |
| Messenger | arm64 patching succeeded, `aapt dump badging` exited 1; arm32 rejected by patch's supported-build guard | Retain metadata verification using direct binary-manifest attributes if badging fails on resource resolution. Add stderr diagnostics. Build arm64 only, as upstream requires. Exact badging stderr was suppressed in the original run, so a fresh build must confirm its specific cause. |
| GameHub | CLI 6 failed loading `app.revanced.patcher.patch.ResourcePatch` | Pin this source to CLI 5.0.1, compatible with its patcher v21 dependency. Reject patch-load errors even if the CLI exits successfully. Newer GameHub app releases still require an actual patching test. |
| WPS Office | Requested `18.24`, downloaded `18.24.1`; patch skipped as incompatible | Require exact release/variant version matching, permitting another provider to supply `18.24`. Do not force the incompatible version. |
| Google News | Requires `5.161.0.931240252`; fallback supplied `5.168.0.982359681`, zero patches | Compatible source version remains unavailable in the observed run. |
| Eyecon | Requires `4.2026.04.05.1300`; fallback supplied `4.2026.09.16.1233`, zero patches | Compatible source version remains unavailable in the observed run. |
| Number / Material Capsule | Pinned `10.3`; every provider failed to obtain that version | Keep the requested version; needs a working authorized source or an explicitly selected different version. |
| The Weather Channel | Requires `16.21.1`; fallback supplied `16.25.0`, zero patches | Compatible source version remains unavailable in the observed run. |
| Aiocal | Hoo bundle applied zero patches; current upstream app list lacks this package | Upstream patch support needed; no zero-patch APK is published. |
| Teuida | Same Hoo source support gap | Upstream patch support needed. |
| Hevy | Brosssh bundle applied zero patches; current source no longer lists this app | Upstream patch support or a verified alternative source needed. |
| Calistree | Same Brosssh source support gap | Upstream patch support or a verified alternative source needed. |

## Primary-source checks

- [ReVanced CLI 6 release](https://github.com/ReVanced/revanced-cli/releases/tag/v6.0.0): explicitly incompatible with patches built against older patcher APIs.
- [GameHub patch dependency](https://github.com/liaralabs/revanced-patches/blob/main/gradle/libs.versions.toml): patcher 21.0.0.
- [HushMessenger supported builds](https://github.com/SysAdminDoc/HushMessenger#supported-messenger-builds): arm64 only, Messenger 583.0.0.29.95 and specified version codes.
- [Hoo supported apps](https://github.com/hoo-dles/morphe-patches#readme) and [Brosssh supported apps](https://github.com/brosssh/morphe-patches#readme): current app lists do not include the four zero-patch entries above.

## Validation and limits

Regression tests reproduce extra native directories, x86 selection, ChromeOS latest-version selection, version-prefix substitution, patch-load errors, and a metadata-reader fallback. Hosted Android smoke tests exercise the binary-manifest parser against a real signed fixture APK. These checks do not prove that every upstream patch will apply to a newly downloaded full app.

After merging, rerun only the affected apps with corrected code. Leave supported-version guards and zero-patch rejection enabled; do not use `force` or `continue_on_error` to turn an unsupported app into an apparently successful release.
