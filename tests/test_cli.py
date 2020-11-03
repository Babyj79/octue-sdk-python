from click.testing import CliRunner

from octue.cli import octue_cli
from tests import TESTS_DIR
from tests.app import CUSTOM_APP_RUN_MESSAGE
from tests.base import BaseTestCase


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
        """Test that an arbitrary run command can be used in the run command of the CLI."""
        result = CliRunner().invoke(
            octue_cli,
            [
                'run',
                f'--app-dir={TESTS_DIR}',
                f'--twine={TESTS_DIR}/data/twines/valid_schema_twine.json',
                f'--config-dir={TESTS_DIR}/data/configuration',
                f'--input-dir={TESTS_DIR}/data/input'
            ]
        )

        assert CUSTOM_APP_RUN_MESSAGE in result.output

    def test_run_command_works_with_data_dir(self):
        """Test that the run command of the CLI works with the --data-dir option."""
        result = CliRunner().invoke(
            octue_cli,
            [
                'run',
                f'--app-dir={TESTS_DIR}',
                f'--twine={TESTS_DIR}/data/twines/valid_schema_twine.json',
                f'--data-dir={TESTS_DIR}/data'
            ]
        )

        assert CUSTOM_APP_RUN_MESSAGE in result.output
