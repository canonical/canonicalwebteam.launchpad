# Standard library
import json
import re
from hashlib import md5


class LaunchpadAuthenticator:
    """
    A base class to providing authentication for making
    requests to the Launchpad API
    """

    def __init__(self, username, token, secret, session):
        """
        This requires a session object because in the normal use-case
        we will be passing through a `talisker.session.get_session()`
        """

        self.username = username
        self.session = session
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Authorization"] = (
            f'OAuth oauth_version="1.0", '
            f'oauth_signature_method="PLAINTEXT", '
            f"oauth_consumer_key={username}, "
            f'oauth_token="{token}", '
            f'oauth_signature="&{secret}"'
        )

    def _request(self, path, method="GET", params={}, data={}):
        """
        Makes a raw HTTP request and returns the response.
        """

        url = f"https://api.launchpad.net/devel/{path}"

        response = self.session.request(method, url, params=params, data=data)
        response.raise_for_status()

        return response


class ImageBuilder(LaunchpadAuthenticator):
    """
    Build ubuntu images through the Launchpad API
    """

    system_codenames = {"16": "xenial", "18": "bionic"}
    board_architectures = {
        "raspberrypi2": {
            "core16": {"arch": "armhf", "subarch": "raspi2"},
            "core18": {"arch": "armhf", "subarch": "raspi3"},
            "classic16.04": {"arch": "armhf", "subarch": "raspi3"},
            "classic18.04": {"arch": "armhf", "subarch": "raspi3"},
        },
        "raspberrypi3": {
            "core16": {"arch": "armhf", "subarch": "raspi3"},
            "core18": {"arch": "armhf", "subarch": "raspi3"},
            "classic16.04": {"arch": "armhf", "subarch": "raspi3"},
            "classic18.04": {"arch": "armhf", "subarch": "raspi3"},
            "classic6418.04": {"arch": "arm64", "subarch": "raspi3"},
        },
        "raspberrypi4": {
            "core18": {"arch": "armhf", "subarch": "raspi3"},
            "classic18.04": {"arch": "armhf", "subarch": "raspi3"},
            "classic6418.04": {"arch": "arm64", "subarch": "raspi3"},
        },
        "intelnuc": {
            "core16": {"arch": "amd64", "subarch": ""},
            "core18": {"arch": "amd64", "subarch": ""},
        },
        "snapdragon": {
            "core16": {"arch": "arm64", "subarch": "snapdragon"},
            "core18": {"arch": "arm64", "subarch": "snapdragon"},
        },
        "cm3": {
            "core16": {"arch": "armhf", "subarch": "cm3"},
            "core18": {"arch": "armhf", "subarch": "raspi3"},
        },
    }

    def build_image(self, board, system, snaps):
        """
        `board` is something like "raspberrypi3",
        `system` is something like "classic6418.04"
        """

        system_year = re.match(r"^[^\d]+(?:64)?(\d{2})(\.\d{2})?$", system)[1]
        codename = self.system_codenames[system_year]
        arch_info = self.board_architectures[board][system]
        project = "ubuntu-core"

        if system.startswith("classic"):
            project = "ubuntu-cpc"

        metadata = {"subarch": arch_info["subarch"], "extra_snaps": snaps}

        data = {
            "ws.op": "requestBuild",
            "pocket": "Updates",
            "archive": "https://api.launchpad.net/1.0/ubuntu/+archive/primary",
            "distro_arch_series": (
                "https://api.launchpad.net/1.0/ubuntu/"
                f"{codename}/{arch_info['arch']}"
            ),
            "metadata_override": json.dumps(metadata),
        }

        return self._request(
            path=(
                f"~{self.username.replace('.', '')}/"
                f"+livefs/ubuntu/{codename}/{project}"
            ),
            method="post",
            data=data,
        )


class SnapBuilder(LaunchpadAuthenticator):
    """
    Methods for building snaps through the Launchpad API
    """

    def get_collection_entries(self, path, params=None):
        """
        Return collection items from the API
        """

        collection = self._request(path=path, params=params)

        return collection.json().get("entries", [])

    def get_snap_by_store_name(self, snap_name):
        """
        Return an Snap from the Launchpad API by store_name
        """

        snaps = self.get_collection_entries(
            path="+snaps",
            params={
                "ws.op": "findByStoreName",
                "owner": f"/~{self.username}",
                "store_name": snap_name,
            },
        )

        # The Launchpad API only allows to find by snaps by store_name
        # but we are only interested in the first one
        if snaps and snaps[0]["store_name"] == snap_name:
            return snaps[0]

        return None

    def create_snap(self, snap_name, git_url):
        """
        Create an ISnap in Launchpad
        """

        data = {
            "ws.op": "new",
            "owner": f"/~{self.username}",
            "name": md5(git_url.encode("UTF-8")).hexdigest(),
            "store_name": snap_name,
            "git_repository_url": git_url,
            "git_path": "HEAD",
            "auto_build": "false",
            "auto_build_archive": "/ubuntu/+archive/primary",
            "auto_build_pocket": "Updates",
            "processors": [
                "/+processors/amd64",
                "/+processors/arm64",
                "/+processors/armhf",
                "/+processors/i386",
                "/+processors/ppc64el",
                "/+processors/s390x",
            ],
            "store_series": "/+snappy-series/16",
        }

        return self._request(path="+snaps", method="POST", data=data)

    def build_snap(self, snap_name):
        """
        Create a new build for a Snap
        """

        lp_snap = self.get_snap_by_store_name(snap_name)

        data = {
            "ws.op": "requestBuild",
            "channels": "snapcraft,apt",
            "archive": (
                "https://api.launchpad.net/devel/ubuntu/+archive/primary"
            ),
            "pocket": "Updates",
        }

        archs = ["amd64", "arm64", "armhf", "i386", "ppc64el", "s390x"]

        for arch in archs:
            data["distro_arch_series"] = f"/ubuntu/xenial/{arch}"
            self._request(
                path=lp_snap["self_link"][32:], method="POST", data=data
            )

        return True
