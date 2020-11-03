from click.testing import CliRunner

from octue.cli import octue_cli
from .base import BaseTestCase


class RunnerTestCase(BaseTestCase):

    def test_version(self):
        """Ensure the version command works in the CLI."""
        result = CliRunner().invoke(octue_cli, ['--version'])
        assert 'version' in result.output

    def test_help(self):
        """Ensure the help commands works in the CLI."""
        help_result = CliRunner().invoke(octue_cli, ['--help'])
        assert help_result.output.startswith('Usage')

        h_result = CliRunner().invoke(octue_cli, ['-h'])
        assert help_result.output == h_result.output

    def test_run_command_can_be_added(self):
        """Test that an arbitrary run command can be added to the CLI via the octue_run decorator."""
        result = CliRunner().invoke(
            octue_cli,
            [   'run',
                '--app-dir=tests',
                '--twine=tests/data/twines/valid_schema_twine.json',
                '--config-dir=tests/data/configuration',
                '--input-dir=tests/data/input'
            ]
        )

        assert result.exception is None
