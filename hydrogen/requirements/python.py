"""Abstractions for dealing with Python package requirements."""
from __future__ import absolute_import

import packaging.requirements

import hydrogen.requirements.base


__all__ = (
    "PythonPackageRequirement",
)


class PythonPackageRequirement(hydrogen.requirements.base.
                               BasePackageRequirement):
    """Represents a PEP 508 Python package requirement."""

    def __init__(self, spec):  # NOQA
        self.requirement = None
        super(PythonPackageRequirement, self).__init__(spec=spec)

    @property
    def is_concrete(self):
        """bool: Indicates that a specific version is pinned."""

    def setup(self):
        """Creates a new :class:`packaging.requirement.Requirement`.

        This method sets :prop:`requirement` to a
        :class:`packaging.requirement.Requirement` object.

        For more information, see the :mod:`packaging` module.

        """
        self.requirement = packaging.requirement.Requirement(self.spec)

    def validate_spec(self, spec):
        """Validates a PEP 508 Python package requirement string."""
        try:
            packaging.requirements.REQUIREMENT.parseString(spec)
            return True
        except packaging.requirements.ParsingException:
            return False
