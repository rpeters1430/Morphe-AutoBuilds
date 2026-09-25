<div align="center">

# 🔧 Morphe Non-Root Builder

[![Daily Build](https://img.shields.io/github/actions/workflow/status/rpeters1430/Morphe-AutoBuilds/patch.yml?label=Daily%20Build&style=for-the-badge&color=2ea44f)](https://github.com/rpeters1430/Morphe-AutoBuilds/actions/workflows/patch.yml)
[![Latest Release](https://img.shields.io/github/v/release/rpeters1430/Morphe-AutoBuilds?style=for-the-badge&label=Latest%20Release&color=0366d6)](https://github.com/rpeters1430/Morphe-AutoBuilds/releases/latest)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/rpeters1430/Morphe-AutoBuilds?style=for-the-badge&color=orange)](LICENSE)


<p align="center">
  <strong>Professional, Automated ReVanced APK Builder</strong><br>
  Multi-source • Multi-architecture • GitHub Actions Powered
</p>

<p align="center">
A sophisticated, automated pipeline that builds ready-to-install Morphe applications for <strong>non-rooted Android devices</strong>. This system automatically fetches the latest Morphe tools, downloads base APKs from multiple sources, applies patches, and publishes optimized APKs with architecture-specific builds.
</p>

[![View Latest Release](https://img.shields.io/badge/View%20Latest%20Release-0A0A0A?style=flat&logo=github&logoColor=white)](https://github.com/rpeters1430/Morphe-AutoBuilds/releases/latest)
[![Report Bug](https://img.shields.io/badge/Report%20Bug-0A0A0A?style=flat&logo=github&logoColor=white)](https://github.com/rpeters1430/Morphe-AutoBuilds/issues)
[![Request Feature](https://img.shields.io/badge/Request%20Feature-0A0A0A?style=flat&logo=github&logoColor=white)](https://github.com/rpeters1430/Morphe-AutoBuilds/issues)


</div>

---

## ⚡ Quick Downloads & App Catalog

> **Note:** All APKs are automatically rebuilt daily at 06:00 UTC to ensure you have the latest features and security patches.

### 📥 Download Links

| Destination | Description | Link |
| :--- | :--- | :--- |
| 🌐 **Interactive Web Portal** | Search apps, filter by arch, scan QR codes on mobile | [**Open App Catalog**](https://rpeters1430.github.io/Morphe-AutoBuilds/) |
| 📦 **GitHub Releases** | Raw release files and assets | [**Download Latest Release**](https://github.com/rpeters1430/Morphe-AutoBuilds/releases/latest) |
| 🔄 **Obtainium Feed** | Every app in one Obtainium import file ([how to use](#-auto-updates-with-obtainium)) | [**apps.json Feed**](https://rpeters1430.github.io/Morphe-AutoBuilds/apps.json) |

---

## 🛠️ Interactive Maintainer Suite (`morphe.py`)

No need to hand-edit JSON configs or memorize GitHub Actions commands! Launch the interactive terminal UI:

```powershell
# On Windows (PowerShell):
.\run.ps1

# Or with Python directly:
python morphe.py
```

**Key Maintainer Features:**
- **📱 App Manager:** Add, edit, disable, or remove apps with auto-complete from `apps/` and `sources/`.
- **🧩 Patch Editor:** Interactively toggle patch inclusions (`+`) and exclusions (`-`) for any app.
- **🚀 CI Dispatcher:** Trigger single-app or full builds on GitHub Actions and watch live streaming logs in your terminal.
- **🔍 Config & Health Validator:** Validate JSON schemas and check that all sources, packages, and keystores are healthy.
- **🔬 Dry-Runner:** Inspect app configuration and source readiness without compiling.
- **🌐 Portal Generator:** Build and preview the GitHub Pages web catalog locally with a single click.

---

### 🔄 Auto-Updates with Obtainium

Every app ships in the same `latest` release, so each Obtainium entry needs a filter that picks out its own APK. The catalog sets this up for you:

* **One app:** open the [App Catalog](https://rpeters1430.github.io/Morphe-AutoBuilds/) on your phone and tap **+ Obtainium** on the app's card.
* **Every app:** download [`apps.json`](https://rpeters1430.github.io/Morphe-AutoBuilds/apps.json), then in Obtainium go to **Import/Export → Obtainium Import** and pick the file.

Each entry comes with these Obtainium settings:

| Setting | Value | Why |
| :--- | :--- | :--- |
| Filter APKs by regular expression | `^<app>-(arm64-v8a\|armeabi-v7a\|universal)-.*\.apk$` | Only offers that app's APKs (e.g. YouTube never matches `youtube-music-…`). |
| Use latest asset upload as release date | on | The release tag is always `latest`, so the upload date of the app's own APK marks a new build. |
| Use release date as version string | on | Lets Obtainium spot an update when only that app was rebuilt. |

> **Added an app before these settings existed?** If Obtainium lists other apps' APKs (e.g. Gboard or Instagram under YouTube) or never sees updates, delete the entry and add it again from the catalog, or set the three settings above by hand in the app's settings in Obtainium.

---

### 📱 Supported Apps & Architectures

Around 100 apps are configured in [`patch-config.json`](patch-config.json); the [App Catalog](https://rpeters1430.github.io/Morphe-AutoBuilds/) lists them all with their current downloads. Apps build as `universal` unless [`arch-config.json`](arch-config.json) asks for specific architectures. Some popular ones:

| Application | Patches | arm64-v8a | armeabi-v7a | Universal |
| :--- | :--- | :---: | :---: | :---: |
| **YouTube** | Morphe | ❌ | ❌ | ✅ |
| **YouTube Music** | Morphe | ✅ | ✅ | ❌ |
| **Reddit** | Morphe | ❌ | ❌ | ✅ |
| **X (Twitter)** | Piko | ❌ | ❌ | ✅ |
| **Instagram** | Piko | ✅ | ❌ | ❌ |
| **Google Photos** | Rookie | ✅ | ✅ | ❌ |
| **TikTok** | IcySymmetra | ❌ | ❌ | ✅ |

*( Legend: ✅ = Available / ❌ = Not configured )*

---

## ✨ Key Features

This repository utilizes a robust Python-based pipeline to ensure high reliability and optimization.

* **Fully Automated:** GitHub Actions workflow executes daily at 06:00 UTC, requiring zero manual intervention.
* **Architecture Optimization:** Builds specific `arm64-v8a`, `armeabi-v7a`, and `universal` APKs to reduce file size and improve performance on target devices.
* **Multi-Source Strategy:** Intelligent fetching from APKMirror, APKPure, and Uptodown ensures high success rates even if one source is down.
* **Granular Patch Control:** Simple text-based configuration allows for precise inclusion or exclusion of specific patches.
* **Smart Failover:** The system automatically switches download sources if a fetch attempt fails.
* **Auto-Signing:** All APKs are signed with a consistent public keystore, making them ready to install immediately.
* **Clean Release Cycle:** Previous releases are replaced rather than archived, preventing clutter and making it easy for external managers (like Orion) to track updates.

---

## 🛠️ Repository Structure

```text
Morphe-AutoBuilds/
├── .github/workflows/      # GitHub Actions automation
│   ├── patch.yml           # Daily automated builds (06:00 UTC)
│   └── manual-patch.yml    # Manual trigger workflow
├── apps/                   # APK source configurations
│   ├── apkmirror/          # APKMirror definitions
│   ├── apkpure/            # APKPure definitions
│   └── uptodown/           # UptoDown definitions
├── patches/                # Patch inclusion/exclusion rules
├── sources/                # ReVanced tool source definitions
├── src/                    # Core Python build logic
├── arch-config.json        # Architecture build matrix (optional)
├── patch-config.json       # App build configuration (apps, patch system, channels)
├── patch-config.schema.json # Editor autocomplete/validation for patch-config.json
└── requirements.txt        # Project dependencies

```

---

## ⚙️ Configuration Guide

This builder is highly configurable. You can adjust the following files to customize the build output.

### 1. App Selection (`patch-config.json`)

Each entry picks an app and the **patch system** (`source`, a file in `sources/`) to build it with. Everything else is optional:

```json
{
  "$schema": "./patch-config.schema.json",
  "defaults": {
    "patches_channel": "stable",
    "experimental": false
  },
  "patch_list": [
    { "app_name": "youtube", "source": "morphe" },
    { "app_name": "youtube-music", "source": "morphe", "patches_channel": "prerelease" },
    { "app_name": "reddit", "source": "morphe", "experimental": true, "arches": ["arm64-v8a"] },
    { "app_name": "instagram", "source": "piko", "exclude_patches": ["Hide ads"] },
    { "app_name": "tiktok", "source": "icysymmetra", "enabled": false }
  ]
}
```

| Field | Default | What it does |
| :--- | :--- | :--- |
| `app_name` | required | App config name in `apps/<platform>/<app_name>.json`. |
| `source` | required | Patch system to use: `sources/<source>.json` (e.g. `morphe`, `piko`, `revanced`). |
| `enabled` | `true` | `false` skips the app without deleting its entry. |
| `patches_channel` | `source` | Which patches release to use: `stable`, `prerelease`, `dev`, `source`, or an exact tag like `v1.4.0`. |
| `cli_channel` | `source` | Same channels, for the patcher CLI. |
| `experimental` | `false` | Morphe only: also consider app versions the patches mark as *experimental*, so you get newer app versions sooner. |
| `force` | `false` | Patch the newest store version even if the patches don't list it as compatible (`--force`). May break the app. |
| `version` | `""` | Pin the app version. Empty picks the newest compatible one. |
| `arches` | from `arch-config.json`, else `["universal"]` | Any of `arm64-v8a`, `armeabi-v7a`, `universal`. |
| `include_patches` / `exclude_patches` | `[]` | Patch names to enable/disable, added to `patches/<app>-<source>.txt`. A patch in both lists stays disabled. |
| `exclusive` | `false` | Apply **only** the patches you enabled (`include_patches`, `patch_options`, `+` rules); every other patch is off (`--exclusive`). |
| `continue_on_error` | `false` | Skip a patch that fails to apply instead of aborting the build (`--continue-on-error`). The APK is built without that patch. |
| `patch_options` | `{}` | Option values per patch, e.g. `{"Change package name": {"packageName": "com.example"}}`. The patch is enabled and each value is passed as `-Okey=value`. |

Example of a hand-picked patch set with options:

```json
{
  "app_name": "youtube",
  "source": "morphe",
  "exclusive": true,
  "include_patches": ["Hide ads", "SponsorBlock", "Return YouTube Dislike"],
  "patch_options": {
    "Custom branding": { "appName": "YouTube Morphe" }
  },
  "continue_on_error": true
}
```

Patch names must match the source exactly. `python morphe.py` → Patch Editor can browse the upstream patch list for the Morphe and ReVanced sources.

**Channels:**
* `stable`: newest normal (non-prerelease) release.
* `prerelease`: newest release of any kind, so you get pre-releases as soon as they are published.
* `dev`: newest release whose tag contains `dev`.
* `source`: keep the `tag` written in `sources/<source>.json` (the behaviour before these options existed).

Settings in `defaults` apply to every entry, and entries can override them. That lets you switch every app to pre-releases in one place and keep a few on stable. Channels apply to GitHub, GitLab and Codeberg sources; bundle sources (`bundle_url`) ignore them.

Changing a channel, `experimental`, `force`, `exclusive`, `continue_on_error`, `patch_options` or the patch lists makes the next daily run rebuild that app. Other apps are left alone.

**Check your config** before pushing (also runs at the start of every daily build):

```bash
python scripts/validate_config.py
```

Editors that support JSON Schema (VS Code, JetBrains) autocomplete and check `patch-config.json` through its `$schema` line.

### 2. Architecture Matrix (`arch-config.json`)

Optional. Sets architectures per app when the entry in `patch-config.json` has no `arches` field.

```json
[
  {
    "app_name": "youtube-music",
    "source": "morphe",
    "arches": ["arm64-v8a", "armeabi-v7a"]
  }
]

```

### 3. Source Definitions

Located in the `apps/` directory. Example for `apps/apkmirror/youtube.json`:

```json
{
  "org": "google-inc",
  "name": "youtube",
  "type": "APK",
  "arch": "universal",
  "dpi": "nodpi",
  "package": "com.google.android.youtube",
  "version": ""
}

```

### 4. Patch Rules

Located in `patches/`. Example for `patches/youtube-morphe.txt`. Use `+` to force include and `-` to exclude.

```text
# Essential patches
+ microg-support
+ premium-heading
+ hide-infocard-suggestions

# Exclusions
- custom-branding
- amoled

```

---

## 🚀 Local Build Instructions

If you prefer to build the APKs on your own machine, follow these steps.

### Prerequisites

* Python 3.11 or higher
* Java Runtime Environment (JRE)
* `zip` utility
* `apksigner` (part of Android SDK Build-Tools)

### Installation & Execution

1. **Clone the repository:**
```bash
git clone https://github.com/rpeters1430/Morphe-AutoBuilds.git
cd Morphe-AutoBuilds

```


2. **Install dependencies:**
```bash
pip install -r requirements.txt

```


3. **Run the build:**
You can build for a specific app and source.
```bash
export APP_NAME="youtube"
export SOURCE="morphe"
python -m src

```


4. **Target specific architecture (Optional):**
```bash
export APP_NAME="youtube"
export SOURCE="morphe"
export ARCH="arm64-v8a"  # Options: arm64-v8a, armeabi-v7a, universal
python -m src

```

5. **Override settings for one build (Optional):**
```bash
export PATCHES_CHANNEL="prerelease"  # stable | prerelease | dev | <tag>
export CLI_CHANNEL="stable"
export EXPERIMENTAL="true"
export FORCE_PATCH="false"
export APP_VERSION="20.12.46"        # pin a version
export CONTINUE_ON_ERROR="true"      # skip patches that fail
export EXCLUSIVE="false"
export INCLUDE_PATCHES="Hide ads, SponsorBlock"   # added to the configured lists
export EXCLUDE_PATCHES="Custom branding"
python -m src

```



---

## 🔄 GitHub Actions Workflows

### Daily Automated Build (`patch.yml`)

* **Schedule:** Runs daily at 06:00 UTC.
* **Function:** Rebuilds only the apps whose patches, CLI, settings or pinned version changed since the last release (incremental).
* **Failing apps:** if an app fails twice with the same patches and settings, the daily run stops retrying it and keeps its previous APK. It is tried again after 7 days, as soon as its patches or settings change, or when you name it in `apps`.
* **Run workflow inputs:**
  * `force_full_rebuild`: rebuild every app.
  * `apps`: rebuild just these apps, e.g. `youtube, reddit`. Everything else in the release is left as it is.
* **Output:** Updates the single "Latest" release tag. The run summary shows the build plan, what was released, and tips for any app that failed.

### Manual Build (`manual-patch.yml`)

* **Trigger:** Manually via the GitHub Actions "Run workflow" button.
* **Capabilities:**
  * Target specific apps. Leave `source` empty to use the one in `patch-config.json`.
  * Target specific architectures (`configured`, the default, uses the app's configured arches).
  * Force specific APK versions.
  * Override for a single run: patches channel or an exact `patches_tag`, CLI channel, `experimental`, `force`, `continue_on_error`.
  * Add patches to enable or disable for this run (`include_patches` / `exclude_patches`, comma-separated).
  * Option to update the public release or just build artifacts.
* **Effect on the daily run:** when the release is updated, the build is recorded in `manifest.json`. A build with the configured settings counts as up to date, so the daily run won't rebuild it. A build with overrides (e.g. a pinned version) is kept until that app's patches or settings change, then replaced by a normal build.

Builds and manual patches share one concurrency group, so they never edit the release at the same time. Only one run waits in the queue: starting another while one is waiting replaces the waiting one.

### App Catalog (`deploy-portal.yml`)

Publishes the web catalog and the Obtainium feed from `docs/` to GitHub Pages. It refreshes after every build, on releases, and when the config changes.

**One-time setup:** open **Settings → Pages** and set **Build and deployment → Source** to **GitHub Actions**. Until then the workflow stops with a message saying so. (Alternatively, add a `PAGES_ENABLEMENT_TOKEN` secret, a fine-grained token with Administration and Pages write access to this repo, and the workflow turns Pages on itself.)



---

## 🤝 Contributing

Contributions to improve the toolchain or add support for new apps are welcome.

1. **Fork** the repository.
2. **Create** a feature branch (`git checkout -b feature/new-app`).
3. **Test** your changes locally using the Python scripts.
4. **Commit** your changes (`git commit -m "Add support for new-app"`).
5. **Push** to the branch (`git push origin feature/new-app`).
6. **Open** a Pull Request.

---

## ⚠️ Disclaimer & Legal

> **Important:** This project is an automated build tool. The APKs provided in the releases are generated automatically using official Morphe tools and patches.

* **Affiliation:** These builds are **not** officially affiliated with the Morphe Team.
* **Usage:** Provided for educational and convenience purposes only. Use at your own risk.
* **GmsCore:** Morphe's MicroG-RE is required for these non-root apps to function correctly.
* **Updates:** Patches are automatically pulled from the latest sources; builds may occasionally contain experimental features.

---

<div align="center">

**If you found this project helpful, please consider giving it a ⭐ Star.**  
<br>
**Made with 💜 by RookieZ**

