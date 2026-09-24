<div align="center">

# 🔧 Morphe Non-Root Builder

[![Daily Build](https://img.shields.io/github/actions/workflow/status/RookieEnough/Revanced-AutoBuilds/patch.yml?label=Daily%20Build&style=for-the-badge&color=2ea44f)](https://github.com/RookieEnough/Revanced-AutoBuilds/actions/workflows/patch.yml)
[![Latest Release](https://img.shields.io/github/v/release/RookieEnough/Revanced-AutoBuilds?style=for-the-badge&label=Latest%20Release&color=0366d6)](https://github.com/RookieEnough/Revanced-AutoBuilds/releases/latest)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/RookieEnough/Revanced-AutoBuilds?style=for-the-badge&color=orange)](LICENSE)


<p align="center">
  <a href="https://ko-fi.com/rookie_z" target="_blank"><img src="https://storage.ko-fi.com/cdn/kofi6.png?v=6" height="30" style="height:30px; border-radius:8px; display:inline-block;" alt="Donate via Ko-fi" /></a>
  &nbsp;&nbsp;
  <a href="https://buymeachai.ezee.li/RookieZ" target="_blank"><img src="https://raw.githubusercontent.com/TakiShiwa/donate-with-upi/ffbb38749891aeb62e758a3692698e346e3df2da/Button/SVG/UPI-light-blue-01.svg" height="30" style="height:30px; border-radius:8px; display:inline-block;" alt="Donate via UPI" /></a>
  <br />
  <a href="https://paypal.me/RookieEnough" target="_blank"><img src="https://raw.githubusercontent.com/stefan-niedermann/paypal-donate-button/master/paypal-donate-button.png" height="50" style="height:50px; border-radius:8px; display:inline-block; margin-top:8px;" alt="Donate via PayPal" /></a>
</p>



<p align="center">
  <strong>Professional, Automated ReVanced APK Builder</strong><br>
  Multi-source • Multi-architecture • GitHub Actions Powered
</p>

<p align="center">
A sophisticated, automated pipeline that builds ready-to-install Morphe applications for <strong>non-rooted Android devices</strong>. This system automatically fetches the latest Morphe tools, downloads base APKs from multiple sources, applies patches, and publishes optimized APKs with architecture-specific builds.
</p>

[![View Latest Release](https://img.shields.io/badge/View%20Latest%20Release-0A0A0A?style=flat&logo=github&logoColor=white)](https://github.com/RookieEnough/Revanced-AutoBuilds/releases/latest)
[![Report Bug](https://img.shields.io/badge/Report%20Bug-0A0A0A?style=flat&logo=github&logoColor=white)](https://github.com/RookieEnough/Revanced-AutoBuilds/issues)
[![Request Feature](https://img.shields.io/badge/Request%20Feature-0A0A0A?style=flat&logo=github&logoColor=white)](https://github.com/RookieEnough/Revanced-AutoBuilds/issues)


</div>

---

## ⚡ Quick Downloads & App Catalog

> **Note:** All APKs are automatically rebuilt daily at 06:00 UTC to ensure you have the latest features and security patches.

### 📥 Download Links

| Destination | Description | Link |
| :--- | :--- | :--- |
| 🌐 **Interactive Web Portal** | Search apps, filter by arch, scan QR codes on mobile | [**Open App Catalog**](https://rpeters1430.github.io/Morphe-AutoBuilds/) |
| 📦 **GitHub Releases** | Raw release files and assets | [**Download Latest Release**](https://github.com/rpeters1430/Morphe-AutoBuilds/releases/latest) |
| 🔄 **Obtainium Feed** | Auto-update directly in Obtainium on Android | [**apps.json Feed**](https://rpeters1430.github.io/Morphe-AutoBuilds/apps.json) |

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

### 📱 Supported Apps & Architectures

| Application | arm64-v8a | armeabi-v7a | Universal |
| :--- | :---: | :---: | :---: |
| **YouTube** | ✅ | ✅ | ✅ |
| **YouTube Music** | ✅ | ✅ | ❌ |
| **Reddit** | ❌ | ❌ | ✅ |
| **Twitter (X)** | ✅ | ❌ | ❌ |
| **TikTok** | ❌ | ❌ | ✅ |
| **Spotify** | ❌ | ❌ | ✅ |

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
revanced-nonroot/
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
| `include_patches` / `exclude_patches` | `[]` | Patch names to enable/disable, added to `patches/<app>-<source>.txt`. |

**Channels:**
* `stable`: newest normal (non-prerelease) release.
* `prerelease`: newest release of any kind, so you get pre-releases as soon as they are published.
* `dev`: newest release whose tag contains `dev`.
* `source`: keep the `tag` written in `sources/<source>.json` (the behaviour before these options existed).

Settings in `defaults` apply to every entry, and entries can override them. That lets you switch every app to pre-releases in one place and keep a few on stable. Channels apply to GitHub, GitLab and Codeberg sources; bundle sources (`bundle_url`) ignore them.

Changing a channel, `experimental`, `force` or the patch lists makes the next daily run rebuild that app. Other apps are left alone.

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
git clone https://github.com/RookieEnough/morphe-AutoBuilds.git
cd morphe-nonroot

```


2. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install requests beautifulsoup4

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
python -m src

```



---

## 🔄 GitHub Actions Workflows

### Daily Automated Build (`patch.yml`)

* **Schedule:** Runs daily at 06:00 UTC.
* **Function:** Iterates through all configured apps and architectures.
* **Output:** Updates the single "Latest" release tag.

### Manual Build (`manual-patch.yml`)

* **Trigger:** Manually via the GitHub Actions "Run workflow" button.
* **Capabilities:**
  * Target specific apps.
  * Target specific architectures (or `configured` to use the app's configured arches).
  * Force specific APK versions.
  * Override the patches channel (`stable` / `prerelease` / `dev`) and the experimental setting for a single run.
  * Option to update the public release or just build artifacts.



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

