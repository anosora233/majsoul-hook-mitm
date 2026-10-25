"""Validate build artifacts and collect the public release assets without publishing."""

import argparse
import hashlib
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_names(version):
    prefix = f"majsoul-hook-{version}"
    packages = {
        "packages-windows-x64": [
            f"{prefix}-windows-x64-portable.zip",
            f"{prefix}-windows-x64-installer.exe",
        ],
        "packages-python": [
            f"majsoul_hook_mitm-{version}-py3-none-any.whl",
            f"majsoul_hook_mitm-{version}.tar.gz",
        ],
    }
    for system in ("macos", "linux"):
        for arch in ("x64", "arm64"):
            packages[f"packages-{system}-{arch}"] = [f"{prefix}-{system}-{arch}-portable.tar.gz"]
    return packages


def prepare_assets(artifacts, output, version):
    packages = package_names(version)
    if {path.name for path in artifacts.iterdir()} != set(packages):
        raise ValueError("Expected the complete set of six package artifacts")
    verified = []
    for artifact, names in packages.items():
        directory = artifacts / artifact
        for name in names:
            source = directory / name
            checksum = directory / (
                "SHA256SUMS" if artifact == "packages-python" else name + ".sha256"
            )
            lines = [line.split() for line in checksum.read_text(encoding="ascii").splitlines()]
            matches = [line[0] for line in lines if len(line) == 2 and line[1] == name]
            with source.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if matches != [digest]:
                raise ValueError(f"Missing or incorrect SHA-256 checksum: {artifact}/{name}")
            verified.append((source, digest))
    # Validate every input before creating output. Copy only named public packages.
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for source, digest in verified:
        shutil.copyfile(source, output / source.name)
        line = f"{digest}  {source.name}\n"
        (output / (source.name + ".sha256")).write_text(line, encoding="ascii")
        manifest.append(line)
    (output / "SHA256SUMS").write_text("".join(sorted(manifest)), encoding="ascii")
    return len(verified)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "build/release-artifacts")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/release")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    if args.tag and args.tag != f"v{version}":
        parser.error("The release tag must match the project version")
    if not (ROOT / "release/notes" / f"v{version}.md").is_file():
        parser.error(f"Missing release notes for v{version}")
    count = prepare_assets(args.artifacts, args.output, version)
    print(f"Verified {count} release packages and their SHA-256 checksums in {args.output}")


if __name__ == "__main__":
    main()
