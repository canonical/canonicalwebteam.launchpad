# Standard library
from os import getenv

# Packages
import requests
from vcr_unittest import VCRTestCase

# Local
from canonicalwebteam.launchpad import Launchpad


class LaunchpadTest(VCRTestCase):
    def _get_vcr_kwargs(self):
        """
        This removes the authorization header
        from VCR so we don't record auth parameters
        """
        return {"filter_headers": ["Authorization"]}

    def setUp(self):
        self.lp_for_snaps = Launchpad(
            username="build.staging.snapcraft.io",
            token=getenv("SNAP_BUILDS_TOKEN", "secret"),
            secret=getenv("SNAP_BUILDS_SECRET", "secret"),
            session=requests.Session(),
        )
        self.lp_for_images = Launchpad(
            username="imagebuild",
            token=getenv("IMAGE_BUILDS_TOKEN", "secret"),
            secret=getenv("IMAGE_BUILDS_SECRET", "secret"),
            session=requests.Session(),
            auth_consumer="image.build",
        )
        return super().setUp()

    def test_01_build_image(self):
        response = self.lp_for_images.build_image(
            board="cm3",
            system="core16",
            snaps=["code", "toto"],
            author_info={"name": "somename", "email": "someemail"},
            gpg_passphrase="fakepassword",
        )

        self.assertEqual(response.status_code, 201)

    def test_02_create_webhooks(self):
        response = self.lp_for_images.create_update_system_build_webhook(
            "classic18.04",
            "https://design.staging.ubuntu.com/?image.build",
            "fake-secret",
        )

        self.assertEqual(response.status_code, 201)

    def test_03_get_snap_by_store_name(self):
        snap = self.lp_for_snaps.get_snap_by_store_name("toto")
        self.assertEqual("toto", snap["store_name"])

        snap = self.lp_for_snaps.get_snap_by_store_name(
            "snap-that-does-not-exist"
        )
        self.assertEqual(None, snap)

    def test_04_create_snap(self):
        snap_name = "new-test-snap"
        git_repo = "https://github.com/build-staging-snapcraft-io/test1"
        self.lp_for_snaps.create_snap(snap_name, git_repo, "macaroon")

        # Check that the snap exist
        new_snap = self.lp_for_snaps.get_snap_by_store_name("new-test-snap")
        self.assertEqual(git_repo, new_snap["git_repository_url"])

    def test_05_build_snap(self):
        result = self.lp_for_snaps.build_snap("toto")
        self.assertEqual(True, result)

    def test_05_delete_snap(self):
        result = self.lp_for_snaps.delete_snap("new-test-snap")
        self.assertEqual(True, result)

    def test_06_get_builders_status(self):
        result = self.lp_for_snaps.get_builders_status()

        for architecture in result.values():
            self.assertIn("pending_jobs", architecture.keys())
            self.assertIn("total_jobs_duration", architecture.keys())
            self.assertIn("estimated_duration", architecture.keys())

    def test_07_get_snap_build_status(self):
        result = self.lp_for_snaps.get_snap_build_status("toto")

        for architecture in result.values():
            self.assertIn("buildstate", architecture.keys())
            self.assertIn("store_upload_status", architecture.keys())
