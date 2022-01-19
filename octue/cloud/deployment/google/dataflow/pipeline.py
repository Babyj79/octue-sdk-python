import logging
import os

import apache_beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.runners.dataflow.dataflow_runner import DataflowRunner
from apache_beam.runners.dataflow.internal.apiclient import DataflowJobAlreadyExistsError

from octue import REPOSITORY_ROOT
from octue.cloud.deployment.google.answer_pub_sub_question import answer_question
from octue.cloud.pub_sub import Topic
from octue.exceptions import DeploymentError


logger = logging.getLogger(__name__)


DEFAULT_IMAGE_URI = "eu.gcr.io/octue-amy/octue-sdk-python:latest"
DEFAULT_DATAFLOW_TEMPORARY_FILES_LOCATION = "gs://octue-sdk-python-dataflow-temporary-data/temp"
DEFAULT_SETUP_FILE_PATH = os.path.join(REPOSITORY_ROOT, "setup.py")


def create_streaming_pipeline(
    service_name,
    service_id,
    project_name,
    region,
    runner="DataflowRunner",
    setup_file_path=DEFAULT_SETUP_FILE_PATH,
    image_uri=DEFAULT_IMAGE_URI,
    temporary_files_location=DEFAULT_DATAFLOW_TEMPORARY_FILES_LOCATION,
    update=False,
    extra_options=None,
):
    """Deploy a streaming Dataflow pipeline to Google Cloud.

    :param str service_name: the name to give the dataflow pipeline
    :param str service_id: the Pub/Sub topic name for the streaming job to subscribe to
    :param str project_name: the name of the project to deploy the pipeline to
    :param str region: the region to deploy the pipeline to
    :param str runner: the name of an apache-beam runner to use to execute the pipeline
    :param str setup_file_path: path to the python `setup.py` file to use for the service
    :param str image_uri: the URI of the apache-beam-based Docker image to use for the pipeline
    :param str temporary_files_location: a Google Cloud Storage path to save temporary files from the service at
    :param bool update: if `True`, update the existing service with the same name
    :param iter|None extra_options: any further arguments in command-line-option format to be passed to Apache Beam as pipeline options
    :return None:
    """
    beam_args = [
        f"--project={project_name}",
        f"--region={region}",
        f"--temp_location={temporary_files_location}",
        f"--job_name={service_name}",
        f"--runner={runner}",
        "--dataflow_service_options=enable_prime",
        f"--setup_file={os.path.abspath(setup_file_path)}",
        "--streaming",
        *(extra_options or []),
    ]

    if image_uri:
        beam_args.append(f"--sdk_container_image={image_uri}")

    if update:
        beam_args.append("--update")

    topic_path = Topic.generate_topic_path(project_name, service_id)

    options = PipelineOptions(beam_args)

    try:
        pipeline = apache_beam.Pipeline(options=options)

        (
            pipeline
            | "Read from Pub/Sub" >> apache_beam.io.ReadFromPubSub(topic=topic_path, with_attributes=True)
            | "Answer question"
            >> apache_beam.Map(lambda question: answer_question(question, project_name=project_name))
        )

        DataflowRunner().run_pipeline(pipeline, options=options)

    except DataflowJobAlreadyExistsError:
        raise DeploymentError(f"A Dataflow job with name {service_name!r} already exists.") from None
