import logging

from octue.resources.analysis import HASH_FUNCTIONS, Analysis
from twined import Twine

from ..base import BaseTestCase


class AnalysisTestCase(BaseTestCase):
    def test_instantiate_analysis(self):
        """Ensures that the base analysis class can be instantiated"""
        # from octue import runner  # <-- instantiated in the library, not here
        analysis = Analysis(twine="{}")
        self.assertEqual(analysis.__class__.__name__, "Analysis")

    def test_instantiate_analysis_with_twine(self):
        """Ensures that the base analysis class can be instantiated"""
        analysis = Analysis(twine=Twine(source="{}"))
        self.assertEqual(analysis.__class__.__name__, "Analysis")

    def test_non_existent_attributes_cannot_be_retrieved(self):
        """Ensure attributes that don't exist on Analysis aren't retrieved as None and instead raise an error. See
        https://github.com/octue/octue-sdk-python/issues/45 for reasoning behind adding this.
        """
        analysis = Analysis(twine=Twine(source="{}"))

        with self.assertRaises(AttributeError):
            analysis.furry_purry_cat

    def test_analysis_hash_attributes_are_none_when_no_relevant_strands(self):
        """Ensures that the hash attributes of Analysis instances are None if none of the relevant strands are provided"""
        analysis = Analysis(twine="{}")
        for strand_name in HASH_FUNCTIONS:
            self.assertIsNone(getattr(analysis, f"{strand_name}_hash"))

    def test_analysis_hash_attributes_are_populated_when_relevant_strands_are_present(self):
        """Ensures that the hash attributes of Analysis instances are valid if the relevant strands are provided."""
        analysis = Analysis(
            twine="{}",
            configuration_values={"resistance_setting": 7},
            configuration_manifest=self.create_valid_manifest(),
            input_values={"quality_factor": 5},
            input_manifest=self.create_valid_manifest(),
        )

        for strand_name in HASH_FUNCTIONS:
            hash_ = getattr(analysis, f"{strand_name}_hash")
            self.assertTrue(isinstance(hash_, str))
            self.assertTrue(len(hash_) == 8)

    def test_warning_raised_if_attempting_to_send_a_monitoring_update_but_no_monitoring_callback_is_provided(self):
        """Test that a warning is raised if attempting to send a monitoring update but no monitoring callback is
        provided.
        """
        analysis = Analysis(twine='{"monitor_message_schema": {}}')

        with self.assertLogs(level=logging.WARNING) as logging_context:
            analysis.send_monitor_message(data=[])

        self.assertIn(
            "Attempted to send a monitor message but no handler is specified.",
            logging_context.output[0],
        )
