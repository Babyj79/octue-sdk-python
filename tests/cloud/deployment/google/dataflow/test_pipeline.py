import os
import unittest

from octue.cloud.pub_sub.service import Service
from octue.resources.service_backends import GCPPubSubBackend
from tests.base import BaseTestCase


@unittest.skipUnless(
    condition=os.getenv("RUN_DEPLOYMENT_TESTS", "").lower() == "true",
    reason="'RUN_DEPLOYMENT_TESTS' environment variable is False or not present.",
)
class TestPipeline(BaseTestCase):
    def test_sending_question_to_dataflow_streaming_job_child(self):
        """Test that a question can be sent to an existing Google Dataflow streaming job child and an answer received
        in response.
        """
        parent = Service(backend=GCPPubSubBackend(project_name=os.environ["TEST_PROJECT_NAME"]))

        subscription, _ = parent.ask(
            service_id="octue.services.pub-sub-dataflow-trial",
            input_values="This is my question for Dataflow.",
            question_uuid="92505713-6052-4e17-b34e-848225ab3acc",
        )

        answer = parent.wait_for_answer(subscription, timeout=3600)
        self.assertIn("output_values", answer)
        self.assertIn("output_manifest", answer)
