import json
import logging
import os

import yaml


logger = logging.getLogger(__name__)


class ServiceConfiguration:
    """A class containing the details needed to configure a service.

    :param str name: the name to give the service
    :param str app_source_path: the path to the directory containing the app's source code
    :param str twine_path: the path to the twine file defining the schema for input, output, and configuration data for the service
    :param str|None app_configuration_path: the path to the app configuration file containing configuration data for the service; if this is `None`, the default application configuration is used
    :return None:
    """

    def __init__(self, name, app_source_path=".", twine_path="twine.json", app_configuration_path=None):
        self.name = name
        self.app_source_path = app_source_path
        self.twine_path = twine_path
        self.app_configuration_path = app_configuration_path

    @classmethod
    def from_file(cls, path):
        """Load a service configuration from a file.

        :param str path:
        :return ServiceConfiguration:
        """
        with open(path) as f:
            raw_service_configuration = yaml.load(f, Loader=yaml.SafeLoader)

        logger.info("Service configuration loaded from %r.", os.path.abspath(path))
        return cls(**raw_service_configuration)


class AppConfiguration:
    """A class containing the configuration data needed to start an app as a service. The configuration data should
    conform to the service's twine schema.

    :param str|None configuration_values: values to configure the app
    :param str|None configuration_manifest: a manifest of files to configure the app
    :param str|None output_manifest_path: the path to give the output manifest
    :param str|None children: details of the children the app requires
    :return None:
    """

    def __init__(
        self,
        configuration_values=None,
        configuration_manifest=None,
        output_manifest_path=None,
        children=None,
    ):
        self.configuration_values = configuration_values
        self.configuration_manifest = configuration_manifest
        self.output_manifest_path = output_manifest_path
        self.children = children

    @classmethod
    def from_file(cls, path):
        """Load an app configuration from a file.

        :param str path:
        :return AppConfiguration:
        """
        with open(path) as f:
            raw_app_configuration = json.load(f)

        logger.info("Service configuration loaded from %r.", os.path.abspath(path))
        return cls(**raw_app_configuration)


def load_service_and_app_configuration(service_configuration_path):
    """Load the service configuration from the given YAML file or return an empty one.

    :param str service_configuration_path: path to service configuration file
    :return dict:
    """
    service_configuration = ServiceConfiguration.from_file(service_configuration_path)
    app_configuration = AppConfiguration()

    if service_configuration.app_configuration_path:
        try:
            app_configuration = AppConfiguration.from_file(service_configuration.app_configuration_path)
        except FileNotFoundError:
            logger.info("No app configuration found.")

    return service_configuration, app_configuration