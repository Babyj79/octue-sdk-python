import datetime
import logging
import os
import tempfile
from google_crc32c import Checksum

from octue.cloud import storage
from octue.cloud.storage import GoogleCloudStorageClient
from octue.cloud.storage.path import CLOUD_STORAGE_PROTOCOL
from octue.exceptions import AttributeConflict, CloudLocationNotSpecified, FileNotFoundException, InvalidInputException
from octue.mixins import Filterable, Hashable, Identifiable, Loggable, Pathable, Serialisable, Taggable
from octue.mixins.hashable import EMPTY_STRING_HASH_VALUE
from octue.utils import isfile
from octue.utils.time import convert_from_posix_time, convert_to_posix_time


module_logger = logging.getLogger(__name__)


TEMPORARY_LOCAL_FILE_CACHE = {}


ID_DEFAULT = None
CLUSTER_DEFAULT = 0
SEQUENCE_DEFAULT = None
TAGS_DEFAULT = None


class Datafile(Taggable, Serialisable, Pathable, Loggable, Identifiable, Hashable, Filterable):
    """Class for representing data files on the Octue system.

    Files in a manifest look like this:

        {
          "path": "folder/subfolder/file_1.csv",
          "cluster": 0,
          "sequence": 0,
          "extension": "csv",
          "tags": "",
          "timestamp": datetime.datetime(2021, 5, 3, 18, 15, 58, 298086),
          "id": "abff07bc-7c19-4ed5-be6d-a6546eae8e86",
          "size_bytes": 59684813,
          "sha-512/256": "somesha"
        },

    :parameter datetime.datetime|int|float|None timestamp: A posix timestamp associated with the file, in seconds since epoch, typically when
        it was created but could relate to a relevant time point for the data
    :param str id: The Universally Unique ID of this file (checked to be valid if not None, generated if None)
    :param logging.Logger logger: A logger instance to which operations with this datafile will be logged. Defaults to
        the module logger.
    :param Union[str, path-like] path: The path of this file, which may include folders or subfolders, within the
        dataset. If no path_from parameter is set, then absolute paths are acceptable, otherwise relative paths are
        required.
    :param Pathable path_from: The root Pathable object (typically a Dataset) that this Datafile's path is relative to.
    :param int cluster: The cluster of files, within a dataset, to which this belongs (default 0)
    :param int sequence: A sequence number of this file within its cluster (if sequences are appropriate)
    :param str tags: Space-separated string of tags relevant to this file
    :param bool skip_checks:

    :return None:
    """

    _SERIALISE_FIELDS = (
        "cluster",
        "id",
        "name",
        "path",
        "sequence",
        "tags",
        "timestamp",
        "_cloud_metadata",
    )

    def __init__(
        self,
        path,
        timestamp,
        id=ID_DEFAULT,
        logger=None,
        path_from=None,
        cluster=CLUSTER_DEFAULT,
        sequence=SEQUENCE_DEFAULT,
        tags=TAGS_DEFAULT,
        skip_checks=True,
        **kwargs,
    ):
        super().__init__(
            id=id,
            name=kwargs.get("name"),
            immutable_hash_value=kwargs.get("immutable_hash_value"),
            logger=logger,
            tags=tags,
            path=path,
            path_from=path_from,
        )

        self.cluster = cluster
        self.sequence = sequence
        self.timestamp = timestamp

        # Set up the file extension or get it from the file path if none passed
        self.extension = self._get_extension_from_path()

        # Run integrity checks on the file
        if not skip_checks:
            self.check(**kwargs)

        self._cloud_metadata = {}

    def __lt__(self, other):
        if not isinstance(other, Datafile):
            raise TypeError(f"An object of type {type(self)} cannot be compared with {type(other)}.")
        return self.absolute_path < other.absolute_path

    def __gt__(self, other):
        if not isinstance(other, Datafile):
            raise TypeError(f"An object of type {type(self)} cannot be compared with {type(other)}.")
        return self.absolute_path > other.absolute_path

    def __repr__(self):
        return f"<{type(self).__name__}({self.name!r})>"

    @classmethod
    def deserialise(cls, serialised_datafile, path_from=None):
        """Deserialise a Datafile from a dictionary. The `path_from` parameter is only used if the path in the
        serialised Dataset is relative.

        :param dict serialised_datafile:
        :param octue.mixins.Pathable path_from:
        :return Datafile:
        """
        cloud_metadata = serialised_datafile.pop("_cloud_metadata", {})

        if not os.path.isabs(serialised_datafile["path"]) and not serialised_datafile["path"].startswith(
            CLOUD_STORAGE_PROTOCOL
        ):
            datafile = Datafile(**serialised_datafile, path_from=path_from)
        else:
            datafile = Datafile(**serialised_datafile)

        datafile._cloud_metadata = cloud_metadata
        return datafile

    @classmethod
    def from_cloud(cls, project_name, bucket_name, datafile_path, allow_overwrite=False, **kwargs):
        """Instantiate a Datafile from a previously-persisted Datafile in Google Cloud storage. To instantiate a
        Datafile from a regular file on Google Cloud storage, the usage is the same, but a meaningful value for each of
        the instantiated Datafile's attributes can be included in the kwargs (a "regular" file is a file that has been
        uploaded to storage without being wrapped in a Datafile instance - i.e. a normal file).

        Note that a value provided for an attribute in kwargs will override any existing value for the attribute.

        :param str project_name:
        :param str bucket_name:
        :param str datafile_path: path to file represented by datafile
        :param bool allow_overwrite: if `True`, allow attributes of the datafile to be overwritten by values given in
            kwargs
        :return Datafile:
        """
        datafile = cls(timestamp=None, path=storage.path.generate_gs_path(bucket_name, datafile_path))

        cloud_metadata = datafile.get_cloud_metadata(project_name, bucket_name, datafile_path)
        custom_metadata = cloud_metadata.get("metadata") or {}

        if not allow_overwrite:
            cls._check_for_attribute_conflict(custom_metadata, **kwargs)

        datafile._set_id(kwargs.get("id", custom_metadata.get("id", ID_DEFAULT)))
        datafile.path = storage.path.generate_gs_path(bucket_name, datafile_path)
        datafile.timestamp = kwargs.get("timestamp", cloud_metadata.get("customTime"))
        datafile.immutable_hash_value = cloud_metadata.get("crc32c", EMPTY_STRING_HASH_VALUE)
        datafile.cluster = kwargs.get("cluster", custom_metadata.get("cluster", CLUSTER_DEFAULT))
        datafile.sequence = kwargs.get("sequence", custom_metadata.get("sequence", SEQUENCE_DEFAULT))
        datafile.tags = kwargs.get("tags", custom_metadata.get("tags", TAGS_DEFAULT))

        datafile._cloud_metadata = cloud_metadata
        datafile._store_cloud_location(project_name, bucket_name, datafile_path)
        return datafile

    def to_cloud(self, project_name=None, bucket_name=None, path_in_bucket=None):
        """Upload a datafile to Google Cloud Storage.

        :param str|None project_name:
        :param str|None bucket_name:
        :param str|None path_in_bucket:
        :return str: gs:// path for datafile
        """
        project_name, bucket_name, path_in_bucket = self._get_cloud_location(project_name, bucket_name, path_in_bucket)
        storage_client = GoogleCloudStorageClient(project_name=project_name)

        cloud_metadata = self.get_cloud_metadata(project_name, bucket_name, path_in_bucket) or {}

        # If the datafile's file has been changed locally, overwrite its cloud copy.
        if cloud_metadata.get("crc32c") != self.hash_value:
            storage_client.upload_file(
                local_path=self.get_local_path(),
                bucket_name=bucket_name,
                path_in_bucket=path_in_bucket,
                metadata=self.metadata(),
            )

        # If the datafile's metadata has been changed locally, update the cloud file's metadata.
        local_metadata = self.metadata()
        timestamp = local_metadata.pop("timestamp")

        if cloud_metadata.get("metadata") != local_metadata or timestamp != cloud_metadata.get("customTime"):
            self.update_cloud_metadata(project_name, bucket_name, path_in_bucket)

        self._store_cloud_location(project_name, bucket_name, path_in_bucket)
        return storage.path.generate_gs_path(bucket_name, path_in_bucket)

    def get_cloud_metadata(self, project_name=None, bucket_name=None, path_in_bucket=None):
        """Get the cloud metadata for the datafile, casting the types of the cluster and sequence fields to integer.

        :param str|None project_name:
        :param str|None bucket_name:
        :param str|None path_in_bucket:
        :return dict:
        """
        project_name, bucket_name, path_in_bucket = self._get_cloud_location(project_name, bucket_name, path_in_bucket)
        cloud_metadata = GoogleCloudStorageClient(project_name).get_metadata(bucket_name, path_in_bucket)

        if cloud_metadata is None:
            return None

        if "metadata" in cloud_metadata:
            if cloud_metadata["metadata"]["cluster"] is not None:
                cloud_metadata["metadata"]["cluster"] = int(cloud_metadata["metadata"]["cluster"])

            if cloud_metadata["metadata"]["sequence"] is not None:
                cloud_metadata["metadata"]["sequence"] = int(cloud_metadata["metadata"]["sequence"])

        return cloud_metadata

    def update_cloud_metadata(self, project_name=None, bucket_name=None, path_in_bucket=None):
        """Update the cloud metadata for the datafile.

        :param str|None project_name:
        :param str|None bucket_name:
        :param str|None path_in_bucket:
        :return None:
        """
        project_name, bucket_name, path_in_bucket = self._get_cloud_location(project_name, bucket_name, path_in_bucket)

        GoogleCloudStorageClient(project_name=project_name).update_metadata(
            bucket_name=bucket_name,
            path_in_bucket=path_in_bucket,
            metadata=self.metadata(),
        )

        self._store_cloud_location(project_name, bucket_name, path_in_bucket)

    @property
    def name(self):
        return self._name or str(os.path.split(self.path)[-1])

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value):
        """Set the datafile's timestamp.

        :param datetime.datetime|int|float|None value:
        :raise TypeError: if value is of an incorrect type
        :return None:
        """
        if isinstance(value, datetime.datetime) or value is None:
            self._timestamp = value
        elif isinstance(value, (int, float)):
            self._timestamp = convert_from_posix_time(value)
        else:
            raise TypeError(
                f"timestamp should be a datetime.datetime instance, an int, a float, or None; received {value!r}"
            )

    @property
    def posix_timestamp(self):
        if self.timestamp is None:
            return None

        return convert_to_posix_time(self.timestamp)

    @property
    def _last_modified(self):
        """Get the date/time the file was last modified in units of seconds since epoch (posix time).

        :return float:
        """
        if self._path_is_in_google_cloud_storage:
            last_modified = self._cloud_metadata.get("updated")

            if last_modified is None:
                return None

            return convert_to_posix_time(last_modified)

        return os.path.getmtime(self.absolute_path)

    @property
    def size_bytes(self):
        if self._path_is_in_google_cloud_storage:
            return self._cloud_metadata.get("size")

        return os.path.getsize(self.absolute_path)

    @property
    def is_in_cloud(self):
        """Does the file exist in the cloud?

        :return bool:
        """
        return self.path.startswith(CLOUD_STORAGE_PROTOCOL)

    def get_local_path(self):
        """Get the local path for the datafile, downloading it from the cloud to a temporary file if necessary. If
        downloaded, the local path is added to a cache to avoid downloading again in the same runtime.

        :raise octue.exceptions.FileLocationError: if the file is not located in the cloud (i.e. it is local)
        :return str:
        """
        if not self.is_in_cloud:
            return self.absolute_path

        if self.absolute_path in TEMPORARY_LOCAL_FILE_CACHE:
            return TEMPORARY_LOCAL_FILE_CACHE[self.absolute_path]

        temporary_local_path = tempfile.NamedTemporaryFile(delete=False).name

        GoogleCloudStorageClient(project_name=self._cloud_metadata["project_name"]).download_to_file(
            *storage.path.split_bucket_name_from_gs_path(self.absolute_path), local_path=temporary_local_path
        )

        TEMPORARY_LOCAL_FILE_CACHE[self.absolute_path] = temporary_local_path
        return temporary_local_path

    def _get_extension_from_path(self, path=None):
        """Gets extension of a file, either from a provided file path or from self.path field"""
        path = path or self.path
        return os.path.splitext(path)[-1].strip(".")

    def _calculate_hash(self):
        """Calculate the hash of the file."""
        hash = Checksum()

        with open(self.get_local_path(), "rb") as f:
            # Read and update hash value in blocks of 4K.
            for byte_block in iter(lambda: f.read(4096), b""):
                hash.update(byte_block)

        return super()._calculate_hash(hash)

    def _get_cloud_location(self, project_name=None, bucket_name=None, path_in_bucket=None):
        """Get the cloud location details for the bucket, allowing the keyword arguments to override any stored values.

        :param str|None project_name:
        :param str|None bucket_name:
        :param str|None path_in_bucket:
        :raise octue.exceptions.CloudLocationNotSpecified: if an exact cloud location isn't provided and isn't available
            implicitly (i.e. the Datafile wasn't loaded from the cloud previously)
        :return (str, str, str):
        """
        try:
            project_name = project_name or self._cloud_metadata["project_name"]
            bucket_name = bucket_name or self._cloud_metadata["bucket_name"]
            path_in_bucket = path_in_bucket or self._cloud_metadata["path_in_bucket"]
        except KeyError:
            raise CloudLocationNotSpecified(
                f"{self!r} wasn't previously loaded from the cloud so doesn't have an implicit cloud location - please"
                f"specify its exact location (its project_name, bucket_name, and path_in_bucket)."
            )

        return project_name, bucket_name, path_in_bucket

    def _store_cloud_location(self, project_name, bucket_name, path_in_bucket):
        """Store the cloud location of the datafile.

        :param str project_name:
        :param str bucket_name:
        :param str path_in_bucket:
        :return None:
        """
        self._cloud_metadata["project_name"] = project_name
        self._cloud_metadata["bucket_name"] = bucket_name
        self._cloud_metadata["path_in_bucket"] = path_in_bucket

    @classmethod
    def _check_for_attribute_conflict(cls, custom_metadata, **kwargs):
        """Raise an error if there is a conflict between the custom metadata and the kwargs.

        :param dict custom_metadata:
        :raise octue.exceptions.AttributeConflict: if any of the custom metadata conflicts with kwargs
        :return None:
        """
        for attribute_name, attribute_value in kwargs.items():

            if custom_metadata.get(attribute_name) == attribute_value:
                continue

            raise AttributeConflict(
                f"The value {custom_metadata.get(attribute_name)!r} of the {cls.__name__} attribute "
                f"{attribute_name!r} conflicts with the value given in kwargs {attribute_value!r}. If you wish to "
                f"overwrite the attribute value, set `allow_overwrite` to `True`."
            )

    def check(self, size_bytes=None, sha=None, last_modified=None, extension=None):
        """Check file presence and integrity"""
        # TODO Check consistency of size_bytes input against self.size_bytes property for a file if we have one
        # TODO Check consistency of sha against file contents if we have a file
        # TODO Check consistency of last_modified date

        if (extension is not None) and not self.path.endswith(extension):
            raise InvalidInputException(
                f"Extension provided ({extension}) does not match file extension (from {self.path}). Pass extension="
                f"None to set extension from filename automatically."
            )

        if not self.exists():
            raise FileNotFoundException(f"No file found at {self.absolute_path}")

    def exists(self):
        """Returns true if the datafile exists on the current system, false otherwise"""
        return isfile(self.absolute_path)

    @property
    def open(self):
        """Context manager to handle the opening and closing of a Datafile.

        If opened in write mode, the manager will attempt to determine if the folder path exists and, if not, will
        create the folder structure required to write the file.

        Use it like:
        ```
        my_datafile = Datafile(timestamp=None, path='subfolder/subsubfolder/my_datafile.json)
        with my_datafile.open('w') as fp:
            fp.write("{}")
        ```
        This is equivalent to the standard python:
        ```
        my_datafile = Datafile(timestamp=None, path='subfolder/subsubfolder/my_datafile.json)
        os.makedirs(os.path.split(my_datafile.absolute_path)[0], exist_ok=True)
        with open(my_datafile.absolute_path, 'w') as fp:
            fp.write("{}")
        ```
        """
        datafile = self

        class DataFileContextManager:
            MODIFICATION_MODES = {"w", "a", "x", "+", "U"}

            def __init__(obj, mode="r", **kwargs):
                obj.mode = mode
                obj.kwargs = kwargs
                obj.fp = None
                obj.path = None

            def __enter__(obj):
                """Open the datafile, first downloading it from the cloud if necessary.

                :return io.TextIOWrapper:
                """
                obj.path = datafile.get_local_path()

                if "w" in obj.mode:
                    os.makedirs(os.path.split(obj.path)[0], exist_ok=True)

                obj.fp = open(obj.path, obj.mode, **obj.kwargs)
                return obj.fp

            def __exit__(obj, *args):
                """Close the datafile, updating the corresponding file in the cloud if necessary.

                :return None:
                """
                if obj.fp is not None:
                    obj.fp.close()

                if datafile.is_in_cloud and any(character in obj.mode for character in obj.MODIFICATION_MODES):
                    datafile.reset_hash()
                    datafile.to_cloud()

        return DataFileContextManager

    def metadata(self):
        """Get the datafile's metadata in a serialised form.

        :return dict:
        """
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "cluster": self.cluster,
            "sequence": self.sequence,
            "tags": self.tags.serialise(to_string=True),
        }
