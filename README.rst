.. This README is meant for consumption by humans and PyPI. PyPI can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on PyPI or github. It is a comment.

.. image:: https://github.com/collective/collective.keycdn/actions/workflows/plone-package.yml/badge.svg
    :target: https://github.com/collective/collective.keycdn/actions/workflows/plone-package.yml

.. image:: https://codecov.io/gh/collective/collective.keycdn/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/collective/collective.keycdn

.. image:: https://img.shields.io/pypi/v/collective.keycdn.svg
    :target: https://pypi.python.org/pypi/collective.keycdn/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/status/collective.keycdn.svg
    :target: https://pypi.python.org/pypi/collective.keycdn
    :alt: Egg Status

.. image:: https://img.shields.io/pypi/pyversions/collective.keycdn.svg?style=plastic   :alt: Supported - Python Versions

.. image:: https://img.shields.io/pypi/l/collective.keycdn.svg
    :target: https://pypi.python.org/pypi/collective.keycdn/
    :alt: License


=================
collective.keycdn
=================

A Plone addon for purging a KeyCDN cache on content changes.

Features
--------

This package overrides the plone.cachepurging utility to send purge requests to KeyCDN, a commercial content delivery network.

It works with the existing caching control panel and a separate add-on control panel for providing api keys and zone configuration information.

Documentation
-------------

This package only works if you have a working plone caching setup. It does not automatically purge content on its own.

Once your caching configuration is in place and you have activated the addon, go to the KeyCDN add on control panel and put in your KeyCDN api key and provide the list of zones and urls to purge.

You can enter multiple zones/sites and each purge will be repeated for each zone.


Installation
------------

Install collective.keycdn by adding it to your buildout::

    [buildout]

    ...

    eggs =
        collective.keycdn


and then running ``bin/buildout``

Once you have installed the package you can enable the addon via the 'Add-ons' control panel.


Authors
-------

Jon Pentland [instification], PretaGov


Contributors
------------

 - instification


Contribute
----------

- Issue Tracker: https://github.com/collective/collective.keycdn/issues
- Source Code: https://github.com/collective/collective.keycdn
- Documentation: https://docs.plone.org/foo/bar


Support
-------

If you are having issues, please create an issue at https://github.com/collective/collective.keycdn/issues


License
-------

The project is licensed under the GPLv2.
