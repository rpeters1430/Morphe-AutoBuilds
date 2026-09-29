# Facebook stock APK for De-Vanced

The De-Vanced prerelease patches currently require Facebook
`580.0.0.51.74` (`com.facebook.katana`). The public store downloaders cannot
reliably supply this older version on GitHub Actions runners.

To activate the configured Facebook build:

1. Obtain the unpatched, complete APK or APK bundle for exactly
   `com.facebook.katana` version `580.0.0.51.74` from a source you trust.
   Check its package and version before publishing it.
2. Create a release in `rpeters1430/Morphe-AutoBuilds` tagged
   `facebook-stock-580`. Attach the stock file with a name containing
   `580.0.0.51.74` and an `.apk`, `.apkm`, or `.xapk` extension. Do not attach
   a patched APK. The GitHub downloader matches the version in the asset name.
3. Set the `facebook` entry in `patch-config.json` to `"enabled": true` and
   run the build. Until then, Facebook remains available for explicit manual
   builds, which fail clearly if no provider supplies the stock APK.

The build rejects damaged archives and validates embedded APKs in bundles,
but source provenance and package/version should be checked before upload.
