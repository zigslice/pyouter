"""Pack skills/ into dist/pyouter-skills-<version>.zip.

The version is the one written in setup.py. The archive keeps the skills/
prefix, so unpacking it at a repository root restores that directory.
"""

import re
import zipfile
from pathlib import Path


def version():
    text = Path("setup.py").read_text(encoding="utf-8")
    found = re.search(r'version\s*=\s*"([^"]+)"', text)
    if not found:
        raise SystemExit("setup.py has no version")
    return found.group(1)


def main():
    root = Path("skills")
    files = [path for path in sorted(root.rglob("*")) if path.is_file()]
    if not files:
        raise SystemExit("skills/ is empty")
    out_dir = Path("dist")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"pyouter-skills-{version()}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.as_posix())
    print(out)


if __name__ == "__main__":
    main()
