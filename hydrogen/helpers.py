"""Miscellaneous utilities."""


__all__ = (
    "abstractclassmethod",
)


# <http://stackoverflow.com/a/11218474/211772>
class abstractclassmethod(classmethod):  # NOQA
    """Ensures that class methods are implemented in concrete classes."""

    __isabstractmethod__ = True

    def __init__(self, callable):  # NOQA
        callable.__isabstractmethod__ = True
        super(abstractclassmethod, self).__init__(callable)
