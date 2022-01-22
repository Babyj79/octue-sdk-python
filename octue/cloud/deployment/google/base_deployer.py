import json
import subprocess
import tempfile
import time
import uuid
from abc import abstractmethod

import yaml

from octue.exceptions import DeploymentError


DOCKER_REGISTRY_URL = "eu.gcr.io"


class BaseDeployer:
    """An abstract tool for using an `octue.yaml` file in a repository to build and deploy the repository's `octue` app.
    This includes setting up a Google Cloud Build trigger, enabling automatic deployment during future development.
    Note that this tool requires the `gcloud` CLI to be available.

    This tool can be inherited from to create specific deployment tools (e.g. for Google Cloud Run or Google Dataflow)
    with the `deploy` and `_generate_cloud_build_configuration` methods overridden to set where and how the app is
    deployed. The `TOTAL_NUMBER_OF_STAGES` class variable should also be overridden and set to the number of stages in
    the subclass's deployment.

    The version information for the version of `gcloud` used to develop this tool is:
    ```
    Google Cloud SDK 367.0.0
    beta 2021.12.10
    bq 2.0.72
    cloud-build-local 0.5.2
    core 2021.12.10
    gsutil 5.5
    pubsub-emulator 0.6.0
    ```

    :param str octue_configuration_path: the path to the `octue.yaml` file if it's not in the current working directory
    :param str|None service_id: the UUID to give the service if a random one is not suitable
    :return None:
    """

    TOTAL_NUMBER_OF_STAGES = None

    def __init__(self, octue_configuration_path, service_id=None):
        self.octue_configuration_path = octue_configuration_path

        with open(self.octue_configuration_path) as f:
            self._octue_configuration = yaml.load(f, Loader=yaml.SafeLoader)

        # Required configuration file entries.
        self.name = self._octue_configuration["name"]
        self.repository_name = self._octue_configuration["repository_name"]
        self.repository_owner = self._octue_configuration["repository_owner"]
        self.project_name = self._octue_configuration["project_name"]
        self.region = self._octue_configuration["region"]

        # Generated attributes.
        self.build_trigger_description = None
        self.generated_cloud_build_configuration = None
        self.service_id = service_id or str(uuid.uuid4())
        self.required_environment_variables = [f"SERVICE_ID={self.service_id}", f"SERVICE_NAME={self.name}"]

        self._default_image_uri = (
            f"{DOCKER_REGISTRY_URL}/{self.project_name}/{self.repository_name}/{self.name}"
            f":{self._get_short_head_commit_hash()}"
        )

        # Optional configuration file entries.
        self.dockerfile_path = self._octue_configuration.get("dockerfile_path")
        self.provided_cloud_build_configuration_path = self._octue_configuration.get("cloud_build_configuration_path")
        self.minimum_instances = self._octue_configuration.get("minimum_instances", 0)
        self.maximum_instances = self._octue_configuration.get("maximum_instances", 10)
        self.concurrency = self._octue_configuration.get("concurrency", 10)
        self.image_uri = self._octue_configuration.get("image_uri", self._default_image_uri)
        self.branch_pattern = self._octue_configuration.get("branch_pattern", "^main$")
        self.memory = self._octue_configuration.get("memory", "128Mi")
        self.cpus = self._octue_configuration.get("cpus", 1)
        self.environment_variables = self._octue_configuration.get("environment_variables", [])

    @abstractmethod
    def deploy(self, no_cache=False, update=False):
        """Deploy the octue app.

        :param bool no_cache: if `True`, don't use the Docker cache when building the image
        :param bool update: if `True`, allow the build trigger to already exist and just build and deploy a new image based on an updated `octue.yaml` file
        :return str: the service's UUID
        """

    @abstractmethod
    def _generate_cloud_build_configuration(self, no_cache=False):
        """Generate a Google Cloud Build configuration equivalent to a `cloudbuild.yaml` file in memory and assign it
        to the `generated_cloud_build_configuration` attribute.

        :param bool no_cache: if `True`, don't use the Docker cache when building the image
        :return None:
        """

    def _create_build_trigger(self, update=False):
        """Create the build trigger in Google Cloud Build using the given `cloudbuild.yaml` file.

        :param bool update: if `True` and there is an existing trigger, delete it and replace it with an updated one
        :return None:
        """
        with ProgressMessage("Creating build trigger", 2, self.TOTAL_NUMBER_OF_STAGES) as progress_message:

            with tempfile.NamedTemporaryFile(delete=False) as temporary_file:
                if self.provided_cloud_build_configuration_path:
                    configuration_option = [f"--build-config={self.provided_cloud_build_configuration_path}"]
                else:
                    # Put the Cloud Build configuration into a temporary file so it can be used by the `gcloud` command.
                    with open(temporary_file.name, "w") as f:
                        yaml.dump(self.generated_cloud_build_configuration, f)

                    configuration_option = [f"--inline-config={temporary_file.name}"]

                create_trigger_command = [
                    "gcloud",
                    f"--project={self.project_name}",
                    "beta",
                    "builds",
                    "triggers",
                    "create",
                    "github",
                    f"--name={self.name}",
                    f"--repo-name={self.repository_name}",
                    f"--repo-owner={self.repository_owner}",
                    f"--description={self.build_trigger_description}",
                    f"--branch-pattern={self.branch_pattern}",
                    *configuration_option,
                ]

                try:
                    self._run_command(create_trigger_command)
                except DeploymentError as e:
                    self._raise_or_ignore_already_exists_error(e, update, progress_message, finish_message="recreated.")

                    delete_trigger_command = [
                        "gcloud",
                        f"--project={self.project_name}",
                        "beta",
                        "builds",
                        "triggers",
                        "delete",
                        f"{self.name}",
                    ]

                    self._run_command(delete_trigger_command)
                    self._run_command(create_trigger_command)

    def _run_build_trigger(self):
        """Run the build trigger and return the build ID. The image URI is updated from the build metadata, ensuring
        that, if a `cloudbuild.yaml` file is provided instead of generated, the correct image URI from this file is
        used in later steps.

        :return str: the build ID
        """
        with ProgressMessage("Running build trigger", 3, self.TOTAL_NUMBER_OF_STAGES):
            build_command = [
                "gcloud",
                f"--project={self.project_name}",
                "--format=json",
                "beta",
                "builds",
                "triggers",
                "run",
                self.name,
                f"--branch={self.branch_pattern.strip('^$')}",
            ]

            process = self._run_command(build_command)
            metadata = json.loads(process.stdout.decode())["metadata"]
            self.image_uri = metadata["build"]["images"][0]
            return metadata["build"]["id"]

    def _wait_for_build_to_finish(self, build_id, check_period=20):
        """Wait for the build with the given ID to finish.

        :param str build_id: the ID of the build to wait for
        :param float check_period: the period in seconds at which to check if the build has finished
        :return: None
        """
        get_build_command = [
            "gcloud",
            f"--project={self.project_name}",
            "--format=json",
            "builds",
            "describe",
            build_id,
        ]

        while True:
            process = self._run_command(get_build_command)
            status = json.loads(process.stdout.decode())["status"]

            if status not in {"WORKING", "SUCCESS"}:
                raise DeploymentError(f"The build status is {status!r}.")

            if status == "SUCCESS":
                break

            time.sleep(check_period)

    @staticmethod
    def _get_short_head_commit_hash():
        """Get the short commit hash for the HEAD commit in the current git repository.

        :return str:
        """
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True).stdout.decode().strip()

    @staticmethod
    def _run_command(command):
        """Run a command in a subprocess, raising a `DeploymentError` if it fails.

        :param iter(str) command: the command to run in `subprocess` form e.g. `["cat", "my_file.txt"]`
        :raise octue.exceptions.DeploymentError: if the command fails
        :return subprocess.CompletedProcess:
        """
        process = subprocess.run(command, capture_output=True)

        if process.returncode != 0:
            raise DeploymentError(process.stderr.decode())

        return process

    @staticmethod
    def _raise_or_ignore_already_exists_error(exception, update, progress_message, finish_message=None):
        """If `update` is `True` and the exception includes the words "already exists", ignore the exception and change
        the progress message's `finish_message` to "already exists."; otherwise, raise the exception.

        :param Exception exception: the exception to ignore or raise
        :param bool update: if `True`, ignore "already exists" errors but raise other errors
        :param ProgressMessage progress_message: the progress message to update with "already exists" if appropriate
        :param str finish_message:
        :raise Exception:
        :return None:
        """
        if update and "already exists" in exception.args[0]:
            progress_message.finish_message = finish_message or "already exists."
            return

        raise exception


class ProgressMessage:
    """A context manager that, on entering the context, prints the given start message and, on leaving it, prints
    "done" on the same line. The use case is to surround a block of code with a start and finish message to give an
    idea of progress on the command line. If multiple progress messages are required, different instances of this class
    can be used and given information on their ordering and the total number of stages to produce an enumerated output.

    For example:
    ```
    [1/4] Generating Google Cloud Build configuration...done.
    [2/4] Creating build trigger...done.
    [3/4] Building and deploying service...done.
    [4/4] Creating Eventarc Pub/Sub run trigger...done.
    ```

    :param str start_message: the message to print before the code in the context is executed
    :param int stage: the position of the progress message among all the related progress messages
    :param int total_number_of_stages: the total number of progress messages that will be printed
    :return None:
    """

    def __init__(self, start_message, stage, total_number_of_stages):
        self.start_message = f"[{stage}/{total_number_of_stages}] {start_message}..."
        self.finish_message = "done."

    def __enter__(self):
        """Print the start message.

        :return ProgressMessage:
        """
        print(self.start_message, end="", flush=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Print the finish message on the same line as the start message. If there's an error, print "ERROR" instead.

        :return None:
        """
        if exc_type:
            print("ERROR.")
        else:
            print(self.finish_message)
