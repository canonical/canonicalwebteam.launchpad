# Standard library
from os import getenv

# Packages
import requests
from vcr_unittest import VCRTestCase

# Local
from canonicalwebteam.launchpad_builds import ImageBuilder


class ImageBuilderTest(VCRTestCase):
    def _get_vcr_kwargs(self):
        """
        This removes the authorization header
        from VCR so we don't record auth parameters
        """
        return {"filter_headers": ["Authorization"]}

    def setUp(self):
        self.client = ImageBuilder(
            username="image.build",
            token=getenv("IMAGE_BUILDER_TOKEN", "secret"),
            secret=getenv("IMAGE_BUILDER_SECRET", "secret"),
            session=requests.Session(),
        )
        return super().setUp()

    def test_01_build_image(self):
        try:
            response = self.client.build_image(
                board="cm3", system="core16", snaps=["code", "toto"]
            )
        except Exception as error:
            import ipdb

            ipdb.set_trace()
            pass

        self.assertEqual(response.status_code, 201)
