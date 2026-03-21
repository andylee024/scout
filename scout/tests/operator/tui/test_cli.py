from click.testing import CliRunner

from scout.main import cli


def test_view_command_is_registered() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["view", "--help"])

    assert result.exit_code == 0
    assert "Launch the Scout lead viewer" in result.output
    assert "--dataset" in result.output


def test_research_command_is_not_registered() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["research", "--help"])

    assert result.exit_code != 0
    assert "No such command 'research'" in result.output
