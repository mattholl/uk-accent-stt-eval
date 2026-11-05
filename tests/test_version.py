import pytest

import ukstt
from ukstt.cli import main


def test_version():
    assert ukstt.__version__ == "0.1.0"


def test_cli_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "0.1.0"


def test_cli_without_subcommand_exits_2(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err
