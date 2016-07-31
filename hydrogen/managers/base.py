"""Base classes for interfacing with package managers."""
import abc

import six


__all__ = (
    "BasePackageManager",
)


@six.add_metaclass(abc.ABCMeta)
class BasePackageManager(object):
    """A base class for a package manager interface."""

    @abc.abstractmethod
    def locate(self):
        """str: Locates the package manager binary or script."""
