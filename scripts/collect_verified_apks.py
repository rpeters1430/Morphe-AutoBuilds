#!/usr/bin/env python3
"""Stage only artifacts whose final verification metadata matches their bytes."""
import hashlib
import json
import shutil
from pathlib import Path


def main() -> int:
    output = Path("verified-apks")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    for apk in sorted(Path(".").glob("*.apk")):
        try:
            meta = json.loads((Path("build_meta") / f"{apk.name}.json").read_text(encoding="utf-8"))
            with apk.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            artifact = meta.get("artifact", {})
            if artifact.get("verified") is not True or artifact.get("sha256") != checksum:
                raise ValueError("missing verification or checksum mismatch")
        except (OSError, ValueError) as error:
            print(f"Not publishing {apk.name}: {error}")
            continue
        shutil.copy2(apk, output / apk.name)
        (output / f"{apk.name}.sha256").write_text(f"{checksum}  {apk.name}\n", encoding="utf-8")
        print(f"Staged verified artifact: {apk.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
