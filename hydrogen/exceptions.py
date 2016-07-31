"""Custom exceptions raised by Hydrogen."""


__all__ = (
    "HydrogenError",
    "InvalidSpecError",
    "PackageManagerLocationError",
)


class HydrogenError(Exception):
    """Base class for all Hydrogen errors."""


class InvalidSpecError(HydrogenError):
    """Indicates an invalid requirements spec."""


class PackageManagerLocationError(HydrogenError):
    """Indicates a package manager was not found on the system."""
