import os
import sys
from setuptools import setup


sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


setup(
    name="hydrogen",
    version=__import__("hydrogen").__version__,
    long_description=__doc__,
    entry_points={
        "console_scripts": ["hydrogen=hydrogen:main"],
    },
)
