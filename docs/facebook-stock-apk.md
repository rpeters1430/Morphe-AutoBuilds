# Facebook stock bundle for De-Vanced

The De-Vanced prerelease patches currently require Facebook `580.0.0.51.74`
(`com.facebook.katana`). The public store downloaders could not reliably
supply this version on GitHub Actions runners.

The selected stock bundle is the [arm64-v8a, Android 11+, 320-640dpi variant](https://www.apkmirror.com/apk/facebook-2/facebook/facebook-580-0-0-51-74-release/facebook-580-0-0-51-74-16-android-apk-download/),
version code `475019369` (BUNDLE 17 S 8a3c). The uploaded `.apkm` archive
contains a base APK and 17 splits. All 18 APK archives passed integrity checks.
The base manifest reports `com.facebook.katana`, version `580.0.0.51.74`,
version code `475019369`, and Android 11 minimum; it has a v2 signature.
The archive SHA-256 is
`1bf782142c05f36ed3d9265e8decd87a2682401da2b90cc0fdcda8430a33ddd4`.

Publish the unpatched bundle as an asset in this repository's release tagged
`facebook-stock-580`. Its asset name must include `580.0.0.51.74` and end
in `.apkm`, for example `facebook-580.0.0.51.74-arm64-v8a.apkm`.
The GitHub downloader selects the asset by version in its name. The Facebook
configuration builds only `arm64-v8a` for this stock variant. Enable its
`patch-config.json` entry after the release asset is available.

The build validates archive structure and embedded APKs, but does not verify
the published asset against this documented SHA-256 automatically.
