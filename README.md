# canonicalwebteam.launchpad-builds

Classes for triggering builds of snaps and images through the launchpad API.

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
