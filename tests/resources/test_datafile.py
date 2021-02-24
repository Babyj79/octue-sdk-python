import copy
import json
import os
import uuid

from octue import exceptions
from octue.mixins import MixinBase, Pathable
from octue.resources import Datafile
from octue.resources.tag import TagSet
from octue.utils.cloud.persistence import OCTUE_MANAGED_CREDENTIALS, GoogleCloudStorageClient
from ..base import BaseTestCase


class MyPathable(Pathable, MixinBase):
    pass


class DatafileTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.path_from = MyPathable(path=os.path.join(self.data_path, "basic_files", "configuration", "test-dataset"))
        self.path = os.path.join("path-within-dataset", "a_test_file.csv")

    def create_valid_datafile(self):
        return Datafile(path_from=self.path_from, base_from=self.path_from, path=self.path, skip_checks=False)

    def test_instantiates(self):
        """Ensures a Datafile instantiates using only a path and generates a uuid ID"""
        df = Datafile(path="a_path")
        self.assertTrue(isinstance(df.id, str))
        self.assertEqual(type(uuid.UUID(df.id)), uuid.UUID)
        self.assertIsNone(df.sequence)
        self.assertEqual(0, df.cluster)

    def test_path_argument_required(self):
        """Ensures instantiation without a path will fail"""
        with self.assertRaises(exceptions.InvalidInputException) as error:
            Datafile()

        self.assertIn("You must supply a valid 'path' for a Datafile", error.exception.args[0])

    def test_checks_fail_when_file_doesnt_exist(self):
        path = "not_a_real_file.csv"
        with self.assertRaises(exceptions.FileNotFoundException) as error:
            Datafile(path=path, skip_checks=False)
        self.assertIn("No file found at", error.exception.args[0])

    def test_conflicting_extension_fails_check(self):
        with self.assertRaises(exceptions.InvalidInputException) as error:
            Datafile(path_from=self.path_from, path=self.path, skip_checks=False, extension="notcsv")

        self.assertIn("Extension provided (notcsv) does not match file extension", error.exception.args[0])

    def test_file_attributes_accessible(self):
        """Ensures that its possible to set the sequence, cluster and timestamp"""
        df = self.create_valid_datafile()
        self.assertIsInstance(df.size_bytes, int)
        self.assertGreaterEqual(df.last_modified, 1598200190.5771205)
        self.assertEqual("a_test_file.csv", df.name)

        df.sequence = 2
        df.cluster = 0
        df.posix_timestamp = 0

    def test_cannot_set_calculated_file_attributes(self):
        """Ensures that calculated attributes cannot be set"""
        df = self.create_valid_datafile()

        with self.assertRaises(AttributeError):
            df.size_bytes = 1

        with self.assertRaises(AttributeError):
            df.last_modified = 1000000000.5771205

    def test_repr(self):
        """ Test that Datafiles are represented as expected. """
        self.assertEqual(repr(self.create_valid_datafile()), "<Datafile('a_test_file.csv')>")

    def test_serialisable(self):
        """Ensures a datafile can serialise to json format"""
        df = self.create_valid_datafile()
        df_dict = df.serialise()

        for k in df_dict.keys():
            self.assertFalse(k.startswith("_"))

        for k in (
            "cluster",
            "extension",
            "id",
            "last_modified",
            "name",
            "path",
            "posix_timestamp",
            "sequence",
            "size_bytes",
            "tags",
            "hash_value",
        ):
            self.assertIn(k, df_dict.keys())

    def test_hash_value(self):
        """ Test hashing a datafile gives a hash of length 128. """
        hash_ = self.create_valid_datafile().hash_value
        self.assertTrue(isinstance(hash_, str))
        self.assertTrue(len(hash_) == 64)

    def test_hashes_for_the_same_datafile_are_the_same(self):
        """ Ensure the hashes for two datafiles that are exactly the same are the same."""
        first_file = self.create_valid_datafile()
        second_file = copy.deepcopy(first_file)
        self.assertEqual(first_file.hash_value, second_file.hash_value)

    def test_from_google_cloud_storage_with_no_metadata(self):
        """Test that a Datafile can be constructed from a file on Google Cloud storage with no custom metadata."""
        project_name = os.environ["TEST_PROJECT_NAME"]
        bucket_name = os.environ["TEST_BUCKET_NAME"]
        path_in_bucket = "file_to_upload.txt"

        GoogleCloudStorageClient(project_name=project_name, credentials=OCTUE_MANAGED_CREDENTIALS).upload_from_string(
            serialised_data=json.dumps({"height": 32}),
            bucket_name=bucket_name,
            path_in_bucket=path_in_bucket,
        )

        datafile = Datafile.from_google_cloud_storage(
            project_name=project_name, bucket_name=bucket_name, path_in_bucket=path_in_bucket
        )

        self.assertEqual(datafile.cluster, 0)
        self.assertEqual(datafile.sequence, None)
        self.assertEqual(datafile.tags, TagSet())
        self.assertTrue(isinstance(datafile.size_bytes, int))
        self.assertTrue(isinstance(datafile.last_modified, float))
        self.assertTrue(isinstance(datafile.hash_value, str))

    def test_from_google_cloud_storage_with_metadata(self):
        """Test that a Datafile can be constructed from a file on Google Cloud storage with custom metadata."""
        project_name = os.environ["TEST_PROJECT_NAME"]
        bucket_name = os.environ["TEST_BUCKET_NAME"]
        path_in_bucket = "file_to_upload.txt"

        GoogleCloudStorageClient(project_name=project_name, credentials=OCTUE_MANAGED_CREDENTIALS).upload_from_string(
            serialised_data=json.dumps({"height": 32}),
            bucket_name=bucket_name,
            path_in_bucket=path_in_bucket,
            metadata={"cluster": 0, "sequence": 1, "tags": ["blah:shah:nah", "blib", "glib"]},
        )

        datafile = Datafile.from_google_cloud_storage(
            project_name=project_name, bucket_name=bucket_name, path_in_bucket=path_in_bucket
        )

        self.assertEqual(datafile.cluster, 0)
        self.assertEqual(datafile.sequence, 1)
        self.assertEqual(datafile.tags, TagSet({"blah:shah:nah", "blib", "glib"}))
        self.assertTrue(isinstance(datafile.size_bytes, int))
        self.assertTrue(isinstance(datafile.last_modified, float))
        self.assertTrue(isinstance(datafile.hash_value, str))
