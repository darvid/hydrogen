"""Base classes for package requirements."""
from __future__ import absolute_import

import abc

import six
import future.utils

import hydrogen.exceptions
import hydrogen.helpers


__all__ = (
    "BasePackageRequirement",
)


@six.add_metaclass(abc.ABCMeta)
class BasePackageRequirement(object):
    """A base class for a package dependency."""

    def __init__(self, spec):
        """Constructs a new requirement.

        Args:
            spec (str): The requirement spec, for example a semver or
                PEP 508 requirement string.

        """
        spec = spec.strip()
        if not self.validate_spec(spec):
            raise hydrogen.exceptions.InvalidSpecError(repr(spec))
        self.spec = spec
        self.setup()

    @abc.abstractproperty
    def is_concrete(self):
        """bool: Indicates that a concrete version is required."""

    @abc.abstractproperty
    def package_manager(self):
        """:class:`BasePackageManager`: The responsible package manager."""

    @hydrogen.helpers.abstractclassmethod
    def validate_spec(cls, spec):  # NOQA
        """bool: Indicates that the specification string is valid."""

    def setup(self):
        """Called by the constructor after initialization."""

    @future.utils.python_2_unicode_compatible
    def __str__(self):  # NOQA
        return self.spec
