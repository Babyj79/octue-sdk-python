import os


TESTS_DIR = os.path.dirname(__file__)
TEST_PROJECT_NAME = os.environ["TEST_PROJECT_NAME"]
TEST_BUCKET_NAME = "octue-test-bucket"


os.environ["USE_OCTUE_LOG_HANDLER"] = "1"
