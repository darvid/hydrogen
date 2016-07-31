#!/usr/bin/env python
"""Hydrogen is a package management workflow tool for Python."""
import sys

import setuptools


def setup():  # NOQA
    requires = ["six", "pbr>=1.9", "setuptools>=17.1"]
    needs_sphinx = {
        "build_sphinx",
        "docs",
        "upload_docs",
    }.intersection(sys.argv)
    if needs_sphinx:
        requires.append("sphinx")
    setuptools.setup(
        setup_requires=requires,
        pbr=True,
    )


if __name__ == "__main__":
    setup()
