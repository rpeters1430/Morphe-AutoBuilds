import json
import logging
import time
from pathlib import Path
from src import (
    utils,
    apkpure,
    session,
    uptodown,
    aptoide,
    apkmirror
)

def _is_retryable_download_error(error: Exception) -> bool:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code in (408, 425, 429, 500, 502, 503, 504):
        return True

    message = str(error).lower()
    retryable_markers = (
        "http error 408",
        "http error 429",
        "http error 500",
        "http error 502",
        "http error 503",
        "http error 504",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "network is unreachable",
    )
    return any(marker in message for marker in retryable_markers)


def download_resource(url: str, name: str = None) -> Path:
    max_attempts = 4
    temp_path: Path | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with session.get(url, stream=True, timeout=180) as res:
                res.raise_for_status()
                final_url = res.url

                resolved_name = name or utils.extract_filename(res, fallback_url=final_url)
                filepath = Path(resolved_name)
                temp_path = filepath.with_suffix(f"{filepath.suffix}.part")
                total_size = int(res.headers.get("content-length", 0))
                downloaded_size = 0

                with temp_path.open("wb") as file:
                    for chunk in res.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)
                            downloaded_size += len(chunk)

                temp_path.replace(filepath)
                logging.info(
                    f"URL: {final_url} [{downloaded_size}/{total_size}] -> \"{filepath}\" [{attempt}]"
                )
                return filepath
        except Exception as e:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

            if attempt < max_attempts and _is_retryable_download_error(e):
                wait_seconds = attempt * 5
                logging.warning(
                    f"Download attempt {attempt}/{max_attempts} failed for {url}: {e}. "
                    f"Retrying in {wait_seconds}s."
                )
                time.sleep(wait_seconds)
                continue
            raise

def load_source_config(source: str) -> dict | list:
    source_path = Path("sources") / f"{source}.json"
    with source_path.open() as json_file:
        return json.load(json_file)

def describe_source(source: str) -> str:
    try:
        source_config = load_source_config(source)
    except FileNotFoundError:
        return "Unknown source"

    if isinstance(source_config, dict) and "bundle_url" in source_config:
        return "Bundle source"

    repo_names = {item.get("repo", "").lower() for item in source_config[1:]}
    if "morphe-cli" in repo_names or "morphe-patches" in repo_names:
        return "Morphe patches"
    if "revanced-cli" in repo_names or "revanced-patches" in repo_names:
        return "ReVanced patches"

    first_name = str(source_config[0].get("name", source)).strip()
    return first_name

def download_required(source: str) -> tuple[list[Path], str]:
    repos_info = load_source_config(source)

    # Handle bundle format
    if isinstance(repos_info, dict) and "bundle_url" in repos_info:
        return download_from_bundle(repos_info)
    
    # Handle old list format
    name = repos_info[0]["name"]
    downloaded_files = []

    for repo_info in repos_info[1:]:
        user = repo_info['user']
        repo = repo_info['repo']
        tag = repo_info['tag']

        release = utils.detect_github_release(user, repo, tag)
        
        # Special handling for Morphe files
        if repo == "morphe-patches" or repo == "morphe-cli":
            for asset in release["assets"]:
                if asset["name"].endswith(".asc"):
                    continue
                # Download .mpp patches or morphe-cli.jar
                if asset["name"].endswith(".mpp") or ("morphe-cli" in asset["name"] and asset["name"].endswith(".jar")):
                    filepath = download_resource(asset["browser_download_url"])
                    downloaded_files.append(filepath)
        else:
            # Original logic for ReVanced files
            for asset in release["assets"]:
                if asset["name"].endswith(".asc"):
                    continue
                filepath = download_resource(asset["browser_download_url"])
                downloaded_files.append(filepath)

    return downloaded_files, name

def download_from_bundle(bundle_info: dict) -> tuple[list[Path], str]:
    """Download resources from a bundle URL"""
    bundle_url = bundle_info["bundle_url"]
    name = bundle_info.get("name", "bundle-patches")
    
    logging.info(f"Downloading bundle from {bundle_url}")
    
    # Download the bundle JSON
    with session.get(bundle_url) as res:
        res.raise_for_status()
        bundle_data = res.json()
    
    downloaded_files = []
    
    # Check API version and structure
    if "patches" in bundle_data:
        # API v4 format
        patches = bundle_data.get("patches", [])
        integrations = bundle_data.get("integrations", [])
        
        # Download patches (JAR files)
        for patch in patches:
            if "url" in patch:
                filepath = download_resource(patch["url"])
                downloaded_files.append(filepath)
                logging.info(f"Downloaded patch: {patch.get('name', 'unknown')}")
        
        # Download integrations (APK files)
        for integration in integrations:
            if "url" in integration:
                filepath = download_resource(integration["url"])
                downloaded_files.append(filepath)
                logging.info(f"Downloaded integration: {integration.get('name', 'unknown')}")
    
    # Also download CLI (still needed) - try ReVanced CLI first
    try:
        cli_release = utils.detect_github_release("revanced", "revanced-cli", "latest")
        for asset in cli_release["assets"]:
            if asset["name"].endswith(".asc"):
                continue
            if asset["name"].endswith(".jar") and "cli" in asset["name"].lower():
                filepath = download_resource(asset["browser_download_url"])
                downloaded_files.append(filepath)
                logging.info("Downloaded ReVanced CLI")
                break
    except Exception as e:
        logging.warning(f"Could not download ReVanced CLI: {e}")
    
    return downloaded_files, name

def download_platform(app_name: str, platform: str, cli: str, patches: str, arch: str = None) -> tuple[Path | None, str | None]:
    try:
        config_path = Path("apps") / platform / f"{app_name}.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with config_path.open() as json_file:
            config = json.load(json_file)
        
        # Override arch if specified
        if arch:
            config['arch'] = arch

        version = config.get("version") or utils.get_supported_version(config['package'], cli, patches)
        platform_module = globals()[platform]
        version = version or platform_module.get_latest_version(app_name, config)
        if not version:
            logging.warning(f"{platform}: could not determine a compatible version for {app_name}")
            return None, None

        download_link = platform_module.get_download_link(version, app_name, config)
        if not download_link:
            logging.warning(f"{platform}: no download link found for {app_name} {version}")
            return None, version

        filepath = download_resource(download_link)
        return filepath, version 

    except FileNotFoundError:
        logging.info(f"{platform}: no config for {app_name}, skipping")
        return None, None
    except Exception as e:
        logging.warning(f"{platform}: failed for {app_name}: {e}")
        return None, None

# Update the specific download functions
def download_apkmirror(app_name: str, cli: str, patches: str, arch: str = None) -> tuple[Path | None, str | None]:
    return download_platform(app_name, "apkmirror", cli, patches, arch)

def download_apkpure(app_name: str, cli: str, patches: str, arch: str = None) -> tuple[Path | None, str | None]:
    return download_platform(app_name, "apkpure", cli, patches, arch)

def download_aptoide(app_name: str, cli: str, patches: str, arch: str = None) -> tuple[Path | None, str | None]:
    return download_platform(app_name, "aptoide", cli, patches, arch)

def download_uptodown(app_name: str, cli: str, patches: str, arch: str = None) -> tuple[Path | None, str | None]:
    return download_platform(app_name, "uptodown", cli, patches, arch)

def download_apkeditor() -> Path:
    release = utils.detect_github_release("REAndroid", "APKEditor", "latest")

    for asset in release["assets"]:
        if asset["name"].startswith("APKEditor") and asset["name"].endswith(".jar"):
            return download_resource(asset["browser_download_url"])

    raise RuntimeError("APKEditor .jar file not found in the latest release")
