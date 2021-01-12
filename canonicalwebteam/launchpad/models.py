# Standard library
import json
import re
from os import getenv
from hashlib import md5

# Packages
import gnupg
from humanize import naturaldelta
from pytimeparse.timeparse import timeparse


LAUNCHPAD_API_URL = getenv(
    "LAUNCHPAD_API_URL", "https://api.launchpad.net/devel/"
)


class Launchpad:
    """
    A collection of actions that can be performed against the Launchpad
    API, coupled with simple authentication logic.

    At the time of writing, this is basically about building snaps
    and building images.
    """

    system_codenames = {"16": "xenial", "18": "bionic"}
    board_architectures = {
        "raspberrypi2": {
            "core16": {"arch": "armhf", "subarch": "raspi2"},
            "core18": {"arch": "armhf", "subarch": "raspi3"},
        },
        "raspberrypi3": {
            "core16": {"arch": "armhf", "subarch": "raspi3"},
            "core18": {"arch": "armhf", "subarch": "raspi3"},
        },
        "raspberrypi4": {"core18": {"arch": "armhf", "subarch": "raspi3"}},
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

    virtual_builders_architectures = [
        "amd64",
        "arm64",
        "armhf",
        "i386",
        "ppc64el",
        "s390x",
    ]

    def __init__(self, username, token, secret, session, auth_consumer=None):
        """
        This requires a session object because in the normal use-case
        we will be passing through a `talisker.session.get_session()`
        """

        if not auth_consumer:
            auth_consumer = username

        self.username = username
        self.session = session
        self.session.headers["Accept"] = "application/json"
        self.session.headers["Authorization"] = (
            f'OAuth oauth_version="1.0", '
            f'oauth_signature_method="PLAINTEXT", '
            f"oauth_consumer_key={auth_consumer}, "
            f'oauth_token="{token}", '
            f'oauth_signature="&{secret}"'
        )

    def request(self, url, method="get", params=None, data=None, json=None):
        """
        Make a request through the configured API session
        """

        response = self.session.request(
            url=url, method=method, params=params, data=data, json=json
        )
        response.raise_for_status()

        return response

    def get_collection_entries(self, url, params=None):
        """
        Return collection items from the API
        """

        return self.request(url, params=params).json().get("entries", [])

    def get_builders_status(self):
        """
        Return virtual builders status in Launchpad
        """
        response = self.request(
            f"{LAUNCHPAD_API_URL}builders",
            params={"ws.op": "getBuildQueueSizes"},
        ).json()

        data = {}
        for arch in self.virtual_builders_architectures:
            # Get total builders
            total_builders = self.request(
                f"{LAUNCHPAD_API_URL}builders",
                params={
                    "ws.op": "getBuildersForQueue",
                    "ws.show": "total_size",
                    "processor": f"/+processors/{arch}",
                    "virtualized": "true",
                },
            ).json()
            total_builders = int(total_builders)

            data[arch] = {}

            # The API could not return an architecture if it doesn't have jobs
            if arch not in response["virt"]:
                data[arch]["pending_jobs"] = 0
                data[arch]["total_jobs_duration"] = None
                data[arch]["estimated_duration"] = None
            else:
                data[arch]["pending_jobs"] = response["virt"][arch][0]
                data[arch]["total_jobs_duration"] = response["virt"][arch][1]
                duration_seconds = timeparse(data[arch]["total_jobs_duration"])

                if total_builders:
                    data[arch]["estimated_duration"] = naturaldelta(
                        duration_seconds / total_builders
                    )
                else:
                    data[arch]["estimated_duration"] = None

        return data

    def create_update_system_build_webhook(self, system, delivery_url, secret):
        """
        Create a webhook for the given system to trigger when a
        build is created or updates, if it doesn't exist already.
        If it exists, raise WebhookExistsError
        """

        system_year = re.match(r"^[^\d]+(?:64)?(\d{2})(\.\d{2})?$", system)[1]
        codename = self.system_codenames[system_year]
        project = "ubuntu-core"
        if system.startswith("classic"):
            project = "ubuntu-cpc"

        webhooks = self.get_collection_entries(
            f"{LAUNCHPAD_API_URL}~{self.username}/"
            f"+livefs/ubuntu/{codename}/{project}/webhooks"
        )

        for webhook in webhooks:
            if (
                webhook["delivery_url"] == delivery_url
                and "livefs:build:0.1" in webhook["event_types"]
            ):
                # If webhook exists, let's update the secret
                return self.request(
                    webhook["self_link"],
                    method="post",
                    data={"ws.op": "setSecret", "secret": secret},
                )

        # Else, create it
        return self.request(
            (
                f"{LAUNCHPAD_API_URL}~{self.username}/"
                f"+livefs/ubuntu/{codename}/{project}"
            ),
            method="post",
            data={
                "ws.op": "newWebhook",
                "delivery_url": delivery_url,
                "event_types": ["livefs:build:0.1"],
                "secret": secret,
            },
        )

    def build_image(
        self, board, system, snaps, author_info, gpg_passphrase, arch=None
    ):
        """
        `board` is something like "raspberrypi3",
        `system` is something like "classic6418.04"
        `arch` is something like "armhf"
        """

        system_year = re.match(r"^[^\d]+(?:64)?(\d{2})(\.\d{2})?$", system)[1]
        codename = self.system_codenames[system_year]
        arch_info = self.board_architectures[board][system]

        if arch:
            arch_info["arch"] = arch

        project = "ubuntu-core"

        if system.startswith("classic"):
            project = "ubuntu-cpc"

        gpg = gnupg.GPG()
        encrypted_author_info = gpg.encrypt(
            json.dumps(author_info),
            recipients=None,
            symmetric="AES256",
            passphrase=gpg_passphrase,
            armor=True,
        )
        metadata = {
            "_author_data": encrypted_author_info.data.decode("utf-8"),
            "subarch": arch_info["subarch"],
            "extra_snaps": snaps,
            "project": project,
            "channel": "stable",
            "image_format": "ubuntu-image",
        }

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

        return self.request(
            (
                f"{LAUNCHPAD_API_URL}~{self.username}/"
                f"+livefs/ubuntu/{codename}/{project}"
            ),
            method="post",
            data=data,
        )

    def get_snap_by_store_name(self, snap_name):
        """
        Return an Snap from the Launchpad API by store_name
        """

        snaps = self.get_collection_entries(
            f"{LAUNCHPAD_API_URL}+snaps",
            params={
                "ws.op": "findByStoreName",
                "owner": f"/~{self.username}",
                "store_name": f'"{snap_name}"',
            },
        )

        # The Launchpad API only allows to find by snaps by store_name
        # but we are only interested in the first one
        if snaps and snaps[0]["store_name"] == snap_name:
            return snaps[0]

        return None

    def get_snap(self, name):
        """
        Return a Snap from the Launchpad API by name
        """

        return self.request(
            f"{LAUNCHPAD_API_URL}~{self.username}/+snap/{name}"
        ).json()

    def create_snap(self, snap_name, git_url, macaroon):
        """
        Create an ISnap in Launchpad
        """

        lp_snap_name = md5(git_url.encode("UTF-8")).hexdigest()

        data = {
            "ws.op": "new",
            "owner": f"/~{self.username}",
            "name": lp_snap_name,
            "store_name": snap_name,
            "git_repository_url": git_url,
            "git_path": "HEAD",
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
            "store_channels": ["edge"],
            "store_upload": "true",
            "auto_build": "false",
        }

        self.request(f"{LAUNCHPAD_API_URL}+snaps", method="post", data=data)

        # Authorize uploads to the store from this user
        data = {"ws.op": "completeAuthorization", "root_macaroon": macaroon}

        self.request(
            f"{LAUNCHPAD_API_URL}~{self.username}/+snap/{lp_snap_name}/",
            method="post",
            data=data,
        )

        return True

    def is_snap_building(self, snap_name):
        """
        Return True is the snap is being build in Launchpad
        """

        lp_snap = self.get_snap_by_store_name(snap_name)
        pending_builds = self.request(
            lp_snap["pending_builds_collection_link"]
        ).json()
        return pending_builds["total_size"] > 0

    def cancel_snap_builds(self, snap_name):
        """
        Cancel the builds if it is either pending or in progress.
        """

        lp_snap = self.get_snap_by_store_name(snap_name)
        builds = self.get_collection_entries(
            lp_snap["pending_builds_collection_link"]
        )

        data = {"ws.op": "cancel"}

        for build in builds:
            self.request(build["self_link"], method="post", data=data)

        return True

    def build_snap(self, snap_name):
        """
        Create a new build for a Snap
        """

        lp_snap = self.get_snap_by_store_name(snap_name)
        channels = lp_snap.get("auto_build_channels")

        data = {
            "ws.op": "requestBuilds",
            "archive": lp_snap["auto_build_archive_link"],
            "pocket": lp_snap["auto_build_pocket"],
        }

        if channels:
            data["channels"] = channels

        self.request(lp_snap["self_link"], method="post", data=data)

        return True

    def get_snap_builds(self, snap_name, pending_builds=True):
        """
        Return list of builds from a Snap from the Launchpad API
        """
        lp_snap = self.get_snap_by_store_name(snap_name)

        builds = self.get_collection_entries(
            lp_snap["completed_builds_collection_link"]
        )

        # Include pending builds
        if pending_builds:
            builds += self.get_collection_entries(
                lp_snap["pending_builds_collection_link"]
            )

        # All of them are ordered by descending creation date
        return sorted(builds, key=lambda x: x["datecreated"], reverse=True)

    def get_snap_build_status(self, snap_name):
        """
        Return build statuses for each arch of the snap
        """
        lp_snap = self.get_snap_by_store_name(snap_name)
        arch_builds = {}

        if lp_snap:
            # We're insterested in the last builds for each architecture
            builds = self.get_snap_builds(
                snap_name,
                pending_builds=True,
            )[: len(self.virtual_builders_architectures)]

            for arch in self.virtual_builders_architectures:
                for build in builds:
                    # Check if the snap build this arch and
                    # the status it's not already set from a recent built
                    if build["arch_tag"] == arch and arch not in arch_builds:
                        arch_builds[arch] = {}
                        arch_builds[arch]["buildstate"] = build["buildstate"]
                        arch_builds[arch]["store_upload_status"] = build[
                            "store_upload_status"
                        ]

        return arch_builds

    def get_snap_build(self, snap_name, build_id):
        """
        Return a Snap Build from the Launchpad API
        """

        lp_snap = self.get_snap_by_store_name(snap_name)

        return self.request(
            f"{LAUNCHPAD_API_URL}~{self.username}"
            f"/+snap/{lp_snap['name']}/+build/{build_id}"
        ).json()

    def get_snap_build_log(self, snap_name, build_id):
        """
        Return the log content of a snap build
        """

        build = self.get_snap_build(snap_name, build_id)

        response = self.request(build["build_log_url"])

        return response.text

    def delete_snap(self, snap_name):
        """
        Delete an ISnap in Launchpad
        """

        lp_snap = self.get_snap_by_store_name(snap_name)

        self.request(lp_snap["self_link"], method="delete")

        return True
