"""Manages interacting with pip for Python package requirements."""
from __future__ import absolute_import

import hydrogen.managers.base


class PipPackageManager(hydrogen.managers.base.BasePackageManager):
    """Interacts with the pip package manager."""

    def locate(self):
        """str: Locates pip."""
