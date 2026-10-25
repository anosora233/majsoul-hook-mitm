import hashlib
import sys

import pytest

from release import prepare_release


@pytest.fixture
def artifacts(tmp_path):
    directory = tmp_path / "artifacts"
    for artifact, names in prepare_release.package_names("0.1.0").items():
        package = directory / artifact
        package.mkdir(parents=True)
        checksums = []
        for name in names:
            content = name.encode("ascii")
            (package / name).write_bytes(content)
            line = f"{hashlib.sha256(content).hexdigest()}  {name}\n"
            if artifact == "packages-python":
                checksums.append(line)
            else:
                (package / (name + ".sha256")).write_text(line, encoding="ascii")
        if checksums:
            (package / "SHA256SUMS").write_text("".join(checksums), encoding="ascii")
        (package / "smoke.json").write_text("{}")
    return directory


def test_release_assets_verify_all_targets_and_exclude_build_metadata(artifacts, tmp_path):
    output = tmp_path / "public"
    assert prepare_release.prepare_assets(artifacts, output, "0.1.0") == 8
    assert len(list(output.iterdir())) == 17
    assert not list(output.glob("*.json"))
    manifest = (output / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    assert len(manifest) == 8
    assert not list(output.glob("*-docker*"))
    for line in manifest:
        digest, name = line.split()
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
        assert (output / (name + ".sha256")).read_text(encoding="ascii").strip() == line


def test_release_rejects_corrupt_package_before_creating_output(artifacts, tmp_path):
    next((artifacts / "packages-python").glob("*.whl")).write_bytes(b"corrupted")
    output = tmp_path / "public"
    with pytest.raises(ValueError, match="incorrect SHA-256"):
        prepare_release.prepare_assets(artifacts, output, "0.1.0")
    assert not output.exists()


def test_release_requires_every_platform_artifact(artifacts, tmp_path):
    (artifacts / "packages-macos-arm64").rename(tmp_path / "omitted")
    output = tmp_path / "public"
    with pytest.raises(ValueError, match="complete set"):
        prepare_release.prepare_assets(artifacts, output, "0.1.0")
    assert not output.exists()


def test_release_rejects_mismatched_tag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prepare_release.py", "--tag", "v999.0.0"])
    with pytest.raises(SystemExit) as error:
        prepare_release.main()
    assert error.value.code == 2
