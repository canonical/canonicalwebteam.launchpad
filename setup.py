#! /usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="canonicalwebteam.launchpad",
    version="0.2.3",
    author="Canonical webteam",
    author_email="webteam@canonical.com",
    url=(
        "https://github.com/canonical-web-and-design/"
        "canonicalwebteam.launchpad"
    ),
    description=(
        "Trigger builds of snaps and ubuntu images"
        "through the launchpad API."
    ),
    packages=find_packages(),
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    tests_require=["vcrpy-unittest"],
)
