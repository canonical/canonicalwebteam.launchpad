# Standard library
from os import getenv

# Packages
import requests
from vcr_unittest import VCRTestCase

# Local
from canonicalwebteam.launchpad import SnapBuilder


class SnapBuilderTest(VCRTestCase):
    def _get_vcr_kwargs(self):
        """
        This removes the authorization header
        from VCR so we don't record auth parameters
        """
        return {"filter_headers": ["Authorization"]}

    def setUp(self):
        self.builder = SnapBuilder(
            username="build.snapcraft.io",
            token=getenv("SNAP_BUILDER_TOKEN", "secret"),
            secret=getenv("SNAP_BUILDER_SECRET", "secret"),
            session=requests.Session(),
        )
        return super().setUp()

    def test_01_get_snap_by_store_name(self):
        snap = self.builder.get_snap_by_store_name("toto")
        self.assertEqual("toto", snap["store_name"])

        snap = self.builder.get_snap_by_store_name("snap-that-does-not-exist")
        self.assertEqual(None, snap)

    def test_02_create_snap(self):
        snap_name = "new-test-snap"
        git_repo = "https://github.com/build-staging-snapcraft-io/test1"
        self.builder.create_snap(snap_name, git_repo)

        # Check that the snap exist
        new_snap = self.builder.get_snap_by_store_name("new-test-snap")
        self.assertEqual(git_repo, new_snap["git_repository_url"])

    def test_03_build_snap(self):
        result = self.builder.build_snap("toto")
        self.assertEqual(True, result)
