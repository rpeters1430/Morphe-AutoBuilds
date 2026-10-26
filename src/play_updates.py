"""Set the Android version-code ceiling used to suppress Play Store updates."""
import os
import struct
import zipfile
from pathlib import Path

MAX_VERSION_CODE = 0x7FFFFFFF
ANDROID_VERSION_CODE_ID = 0x0101021B


def _manifest_with_max_version_code(data: bytes) -> bytes:
    """Return a binary Android manifest with android:versionCode capped."""
    result = bytearray(data)
    if len(result) < 8 or struct.unpack_from("<HHI", result) != (3, 8, len(result)):
        raise ValueError("Invalid binary AndroidManifest.xml header")

    version_index = None
    root_seen = False
    changed = False
    offset = 8

    while offset < len(result):
        if offset + 8 > len(result):
            raise ValueError("Truncated XML chunk header")
        kind, header, size = struct.unpack_from("<HHI", result, offset)
        if header < 8 or size < header or offset + size > len(result):
            raise ValueError("Invalid XML chunk bounds")

        if kind == 0x0180:  # RES_XML_RESOURCE_MAP_TYPE
            if header != 8 or (size - header) % 4 or root_seen:
                raise ValueError("Invalid XML resource map")
            matches = [
                index
                for index in range((size - header) // 4)
                if struct.unpack_from("<I", result, offset + header + index * 4)[0]
                == ANDROID_VERSION_CODE_ID
            ]
            if len(matches) > 1 or (matches and version_index is not None):
                raise ValueError("Duplicate android:versionCode resource mapping")
            if matches:
                version_index = matches[0]

        elif kind == 0x0102 and not root_seen:  # RES_XML_START_ELEMENT_TYPE
            root_seen = True
            if header != 16 or size < header + 20:
                raise ValueError("Invalid manifest root element")

            extension = offset + header
            attribute_start, attribute_size, attribute_count = struct.unpack_from(
                "<HHH", result, extension + 8
            )
            if (
                attribute_start < 20
                or attribute_size != 20
                or header + attribute_start + attribute_size * attribute_count > size
            ):
                raise ValueError("Invalid manifest attributes")

            if version_index is not None:
                for index in range(attribute_count):
                    attribute = extension + attribute_start + index * attribute_size
                    namespace, name, _raw, value_size, reserved, value_type, _value = (
                        struct.unpack_from("<IIIHBBI", result, attribute)
                    )
                    if name != version_index:
                        continue
                    if (
                        changed
                        or namespace == 0xFFFFFFFF
                        or value_size != 8
                        or reserved
                        or value_type not in (0x10, 0x11)
                    ):
                        raise ValueError("Invalid android:versionCode attribute")

                    # Clear the raw string so it cannot contradict the integer value.
                    struct.pack_into("<I", result, attribute + 8, 0xFFFFFFFF)
                    struct.pack_into("<I", result, attribute + 16, MAX_VERSION_CODE)
                    changed = True

        offset += size

    if not root_seen or not changed:
        raise ValueError("Manifest has no integer android:versionCode")
    return bytes(result)


def disable_play_store_updates(apk: Path) -> None:
    """Rewrite versionCode atomically; the caller must align and sign afterward."""
    temporary = apk.with_suffix(".no-play-updates.tmp")
    try:
        with zipfile.ZipFile(apk, "r") as source:
            if source.namelist().count("AndroidManifest.xml") != 1:
                raise ValueError("APK must contain exactly one AndroidManifest.xml")
            manifest = _manifest_with_max_version_code(source.read("AndroidManifest.xml"))
            with zipfile.ZipFile(temporary, "w") as target:
                target.comment = source.comment
                for entry in source.infolist():
                    payload = manifest if entry.filename == "AndroidManifest.xml" else source.read(entry)
                    target.writestr(entry, payload)
        os.replace(temporary, apk)
    finally:
        temporary.unlink(missing_ok=True)
