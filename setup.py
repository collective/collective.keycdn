# -*- coding: utf-8 -*-
"""Installer for the collective.keycdn package."""

from setuptools import find_packages
from setuptools import setup


long_description = "\n\n".join(
    [
        open("README.rst").read(),
        open("CONTRIBUTORS.rst").read(),
        open("CHANGES.rst").read(),
    ]
)


setup(
    name="collective.keycdn",
    version="1.0.0",
    description="A Plone addon for purging a KeyCDN cache on content changes.",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 5.2",
        "Framework :: Plone :: 6.0",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords="Python Plone CMS KeyCDN",
    author="Jon Pentland",
    author_email="jon.pentland@pretagov.co.uk",
    url="https://github.com/collective/collective.keycdn",
    project_urls={
        "PyPI": "https://pypi.org/project/collective.keycdn/",
        "Source": "https://github.com/collective/collective.keycdn",
        "Tracker": "https://github.com/collective/collective.keycdn/issues",
        # 'Documentation': 'https://collective.keycdn.readthedocs.io/en/latest/',
    },
    license="GPL version 2",
    packages=find_packages("src", exclude=["ez_setup"]),
    namespace_packages=["collective"],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.7",
    install_requires=[
        "setuptools",
        # -*- Extra requirements: -*-
        "z3c.jbot",
        "z3c.unconfigure",
        "plone.api>=1.8.4",
        "plone.app.dexterity",
        "plone.cachepurging",
        "requests>=2.20.0",
    ],
    extras_require={
        "test": [
            "plone.app.testing",
            "plone.testing>=5.0.0",
            "plone.app.contenttypes",
            "plone.restapi",
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = collective.keycdn.locales.update:update_locale
    """,
)
