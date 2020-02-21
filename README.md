# canonicalwebteam.launchpad

Classes for triggering builds of snaps and Ubuntu images through the [Launchpad API](https://launchpad.net/+apidoc/devel.html).

## Usage

### SnapBuilder

``` python3
from canonicalwebteam.launchpad import SnapBuilder

snap_builder = SnapBuilder(
    username="build.snapcraft.io",
    token=os.getenv("SNAP_BUILDER_TOKEN"),
    secret=os.getenv("SNAP_BUILDER_SECRET"),
)

snap_name = "new-test-snap"
git_repo = "https://github.com/build-staging-snapcraft-io/test1"
snap_builder.create_snap(snap_name, git_repo)

new_snap = snap_builder.get_snap_by_store_name("new-test-snap")
```

### ImageBuilder

``` python3
from canonicalwebteam.launchpad import ImageBuilder

image_builder = ImageBuilder(
    username="image.build",
    token=os.getenv("IMAGE_BUILDER_TOKEN"),
    secret=os.getenv("IMAGE_BUILDER_SECRET"),
)

image_builder.build_image(
    board="cm3", system="core16", snaps=["code", "toto"]
)
```

## Test fixtures

Tests check calls against fixtures representing the Launchpad API. These fixtures are generated using [vcrpy](https://pypi.org/project/vcrpy/), based on real calls to the API when the test was first run.

To new tests that rely on new API responses, or if we need to regenerate existing fixtures because the API has changed, the secrets need to be provided to authenticate with the API as follows:

``` bash
export SNAP_BUILDER_TOKEN={token}
export SNAP_BUILDER_SECRET={secret}
export IMAGE_BUILDER_TOKEN={token}
export IMAGE_BUILDER_SECRET={secret}

rm tests/cassettes/...  # Remove any fixtures you need to regenerate

./setup.py test  # Run tests again to regenerate fixtures
```
