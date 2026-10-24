from unittest.mock import AsyncMock

import pytest

from majsoul_hook.cli import capture_process, main


@pytest.mark.parametrize("process", ["", "!chrome", "chrome,firefox", ":123", "x\ny"])
def test_reject_broad_capture(process):
    with pytest.raises(ValueError):
        capture_process(process)


def test_cli_forwards_only_supported_options(schema, monkeypatch, tmp_path):
    monkeypatch.setattr("majsoul_hook.cli.Schema.load", lambda path: schema)
    capture = AsyncMock()
    monkeypatch.setattr("majsoul_hook.runtime.run_capture", capture)
    main(
        [
            "capture",
            "--process",
            " 1234 ",
            "--host",
            "Example.COM.",
            "--confdir",
            str(tmp_path),
            "--verbose",
        ]
    )
    capture.assert_awaited_once_with(
        "1234",
        schema,
        hosts=("example.com",),
        confdir=tmp_path,
        output=None,
        verbose=True,
        cosmetics=None,
    )


def test_cli_cosmetics_requires_configuration(schema, monkeypatch):
    monkeypatch.setattr("majsoul_hook.cli.Schema.load", lambda path: schema)
    capture = AsyncMock()
    monkeypatch.setattr("majsoul_hook.runtime.run_capture", capture)
    with pytest.raises(SystemExit) as error:
        main(["capture", "--process", "1234", "--cosmetics"])
    assert error.value.code == 1
    capture.assert_not_called()


def test_cli_explicit_cosmetics(cosmetic_schema, cosmetic_config, monkeypatch, tmp_path):
    from majsoul_hook.cosmetics import Cosmetics

    cosmetic_schema.cosmetic_config = cosmetic_config
    monkeypatch.setattr("majsoul_hook.cli.Schema.load", lambda path: cosmetic_schema)
    capture = AsyncMock()
    monkeypatch.setattr("majsoul_hook.runtime.run_capture", capture)
    main(["capture", "--process", "1234", "--cosmetics", "--state", str(tmp_path / "state.json")])
    assert isinstance(capture.await_args.kwargs["cosmetics"], Cosmetics)
    assert capture.await_args.kwargs["cosmetics"].store.path == tmp_path / "state.json"
