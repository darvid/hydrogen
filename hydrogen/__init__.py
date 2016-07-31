# -*- coding: utf-8 -*-
"""Hydrogen is a package management workflow tool for Python."""
import pkg_resources


try:
    __version__ = pkg_resources.get_distribution(__name__).version
except:
    __version__ = "unknown"
