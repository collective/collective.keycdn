# -*- coding: utf-8 -*-
"""KeyCDN cache purger implementation."""

from collective.keycdn.interfaces import IKeycdnPurgingSettings
from plone.cachepurging.interfaces import IPurger
from plone.cachepurging.purger import DEFAULT_PURGER as ORIGINAL_DEFAULT_PURGER
from plone.registry.interfaces import IRegistry
from urllib.parse import urlparse
from zope.component import queryUtility
from zope.interface import implementer

import atexit
import base64
import json
import logging
import queue
import requests
import threading
import time


logger = logging.getLogger(__name__)


@implementer(IPurger)
class KeycdnPurger:
    """Purger implementation for KeyCDN API.

    Similar to DefaultPurger, uses asynchronous worker threads but
    batches URLs and sends to KeyCDN API instead of HTTP PURGE.
    """

    def __init__(self):
        """Initialize purger with thread-safe data structures."""
        self.queue = queue.Queue(maxsize=1000)
        self.worker = None
        self.queueLock = threading.Lock()
        self.stopping = False

    def _get_settings(self):
        """Retrieve KeyCDN settings from registry."""
        registry = queryUtility(IRegistry)
        if registry is None:
            return None
        try:
            return registry.forInterface(IKeycdnPurgingSettings, check=False)
        except KeyError:
            logger.warning("KeyCDN settings not found in registry")
            return None

    def _is_installed(self):
        """Check if collective.keycdn package is installed.

        We check if the GenericSetup profile has been applied by looking
        for our control panel action in portal_controlpanel.

        Returns:
            bool: True if installed, False otherwise
        """
        try:
            from plone import api

            controlpanel = api.portal.get_tool("portal_controlpanel")
            actions = [a.getId() for a in controlpanel.listActions()]
            return "keycdn" in actions
        except Exception:
            # If we can't check (no portal, etc), assume not installed
            return False

    def _should_use_keycdn(self):
        """Determine if KeyCDN purger should be used.

        KeyCDN is used only when:
        1. The package is installed (control panel exists)
        2. The 'enabled' setting is True

        Returns:
            bool: True to use KeyCDN, False to delegate to original purger
        """
        # Check if installed first
        if not self._is_installed():
            return False

        # Check if enabled in settings
        settings = self._get_settings()
        if not settings or not settings.enabled:
            return False

        return True

    def _get_auth_header(self, api_key):
        """Generate HTTP Basic Auth header for KeyCDN API."""
        # KeyCDN uses API key as username, empty password
        auth_string = f"{api_key}:"
        encoded = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded}"

    def _parse_zones(self, zones_setting):
        """Parse zone_id|base_domain strings into list of tuples.

        Args:
            zones_setting: Tuple of strings like "12345|https://example.com"

        Returns:
            List of (zone_id, base_domain) tuples
        """
        zones = []
        if not zones_setting:
            return zones

        for zone_str in zones_setting:
            if not zone_str or "|" not in zone_str:
                logger.warning(
                    f"Invalid zone format (expected 'zone_id|domain'): {zone_str}"
                )
                continue

            parts = zone_str.split("|", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid zone format: {zone_str}")
                continue

            zone_id, base_domain = parts
            zone_id = zone_id.strip()
            base_domain = base_domain.strip()

            if not zone_id or not base_domain:
                logger.warning(f"Empty zone_id or base_domain in: {zone_str}")
                continue

            zones.append((zone_id, base_domain))

        return zones

    def _extract_path(self, url):
        """Extract path from URL (handles both absolute URLs and paths).

        Args:
            url: Either "/path" or "https://example.com/path"

        Returns:
            Path string starting with /
        """
        if url.startswith("/"):
            return url

        parsed = urlparse(url)
        path = parsed.path
        if parsed.query:
            path += "?" + parsed.query
        if parsed.fragment:
            path += "#" + parsed.fragment

        return path if path else "/"

    def _purge_batch(self, session, urls, zone_id, api_key):
        """Purge a batch of URLs via KeyCDN API.

        Args:
            session: requests.Session
            urls: List of absolute URLs to purge
            zone_id: KeyCDN zone ID
            api_key: KeyCDN API key

        Returns:
            Tuple (success: bool, response_data: dict, error: str)
        """
        if not urls:
            return True, {}, ""

        api_url = f"https://api.keycdn.com/zones/purgeurl/{zone_id}.json"
        headers = {
            "Authorization": self._get_auth_header(api_key),
            "Content-Type": "application/json",
        }
        payload = {"urls": list(urls)}

        try:
            logger.debug(f"Purging {len(urls)} URLs via KeyCDN API for zone {zone_id}")
            resp = session.delete(api_url, headers=headers, json=payload, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                logger.info(
                    f"KeyCDN purge successful for zone {zone_id}: {len(urls)} URLs"
                )
                logger.debug(f"KeyCDN response: {data}")
                return True, data, ""
            else:
                error = f"KeyCDN API error {resp.status_code}: {resp.text}"
                logger.error(error)
                return False, {}, error

        except Exception as e:
            error = f"KeyCDN API request failed: {e}"
            logger.exception(error)
            return False, {}, error

    def purgeSync(self, url, httpVerb="PURGE"):
        """Purge URL synchronously via KeyCDN API or delegate to original.

        Args:
            url: URL or path to purge
            httpVerb: HTTP verb to use (KeyCDN ignores this)

        Returns:
            Tuple (status, xcache, xerror) for compatibility with IPurger
        """
        logger.debug(f"KeyCDN purgeSync called for: {url}")

        # Delegate to original purger if not installed or not enabled
        if not self._should_use_keycdn():
            logger.debug("KeyCDN not active, delegating to original purger")
            return ORIGINAL_DEFAULT_PURGER.purgeSync(url, httpVerb)

        # KeyCDN is active - proceed with KeyCDN purging
        settings = self._get_settings()

        if not settings.api_key:
            return "ERROR", "", "KeyCDN API key not configured"

        zones = self._parse_zones(settings.zones)
        if not zones:
            return "ERROR", "", "No KeyCDN zones configured"

        # Extract path from URL
        path = self._extract_path(url)

        # Purge in all zones
        results = []
        errors = []

        try:
            with requests.Session() as session:
                for zone_id, base_domain in zones:
                    # Generate full URL for this zone
                    full_url = base_domain.rstrip("/") + path

                    success, data, error = self._purge_batch(
                        session, [full_url], zone_id, settings.api_key
                    )

                    results.append((zone_id, success, data))
                    if not success:
                        errors.append(f"Zone {zone_id}: {error}")

                # Return aggregate status
                all_success = all(success for _, success, _ in results)
                status = 200 if all_success else "ERROR"
                xcache = json.dumps(
                    {
                        "zones": [
                            {"zone_id": zid, "success": success, "data": data}
                            for zid, success, data in results
                        ]
                    }
                )
                xerror = "; ".join(errors) if errors else ""

                return status, xcache, xerror

        except Exception as e:
            logger.exception(f"Sync purge failed for {url}")
            return "ERROR", "", str(e)

    def purgeAsync(self, url, httpVerb="PURGE"):
        """Queue URL path for asynchronous purging or delegate to original.

        The path will be expanded to full URLs for all configured zones
        by the worker thread if KeyCDN is active. Otherwise delegates
        to the original DEFAULT_PURGER.

        Args:
            url: URL or path to purge
            httpVerb: HTTP verb (KeyCDN ignores this)
        """
        logger.debug(f"KeyCDN purgeAsync queuing: {url}")

        # Delegate to original purger if not installed or not enabled
        if not self._should_use_keycdn():
            logger.info("KeyCDN not active, delegating to original purger")
            return ORIGINAL_DEFAULT_PURGER.purgeAsync(url, httpVerb)

        # KeyCDN is active - proceed with KeyCDN purging
        settings = self._get_settings()

        if not settings.api_key:
            logger.warning("KeyCDN API key not configured, skipping purge")
            return

        zones = self._parse_zones(settings.zones)
        if not zones:
            logger.warning("No KeyCDN zones configured, skipping purge")
            return

        # Extract path from URL
        path = self._extract_path(url)

        # Ensure worker thread is running
        self._ensure_worker(settings)

        try:
            self.queue.put(path, block=False)
            logger.debug(f"Queued for purge: {path}")
        except queue.Full:
            logger.warning(f"Purge queue full, discarding: {path}")

    def _ensure_worker(self, settings):
        """Ensure worker thread is running.

        Args:
            settings: IKeycdnPurgingSettings instance
        """
        if self.worker is None or not self.worker.is_alive():
            with self.queueLock:
                if self.worker is None or not self.worker.is_alive():
                    logger.debug("Starting KeyCDN purge worker thread")
                    self.worker = KeycdnWorker(self, settings)
                    self.worker.start()

    def stopThreads(self, wait=False):
        """Stop worker thread for KeyCDN and original purger.

        Args:
            wait: If True, wait for threads to finish

        Returns:
            True if successful, False if timeout
        """
        # Stop KeyCDN worker
        self.stopping = True

        # Wake up KeyCDN worker if sleeping
        try:
            self.queue.put(None, block=False)
        except queue.Full:
            pass

        if wait and self.worker:
            self.worker.join(5)
            if self.worker.is_alive():
                logger.warning("KeyCDN worker thread failed to terminate")
                return False

        # Also stop original purger's threads
        try:
            ORIGINAL_DEFAULT_PURGER.stopThreads(wait=wait)
        except Exception as e:
            logger.warning(f"Failed to stop original purger threads: {e}")

        return True

    @property
    def http_1_1(self):
        """Compatibility property from IPurger interface."""
        return True

    @property
    def errorHeaders(self):
        """Compatibility property from IPurger interface."""
        return ()


class KeycdnWorker(threading.Thread):
    """Worker thread for batched asynchronous KeyCDN purging."""

    def __init__(self, purger, settings):
        """Initialize worker.

        Args:
            purger: KeycdnPurger instance
            settings: IKeycdnPurgingSettings instance
        """
        super().__init__(name="KeycdnPurgeWorker")
        self.purger = purger
        self.settings = settings
        self.daemon = True

    def run(self):
        """Process purge queue, batching URLs per zone for efficiency."""
        logger.debug("KeyCDN worker thread starting")
        atexit.register(self.purger.stopThreads)

        batch_size = self.settings.batch_size

        try:
            with requests.Session() as session:
                # Per-zone batches: {zone_id: set of URLs}
                zone_batches = {}
                last_flush = time.time()

                while not self.purger.stopping:
                    try:
                        # Wait up to 1 second for items
                        path = self.purger.queue.get(timeout=1.0)

                        if path is None or self.purger.stopping:
                            # Shutdown signal
                            break

                        # Expand path to all zones
                        zones = self.purger._parse_zones(self.settings.zones)
                        logger.debug(f"Expanding path {path} to {len(zones)} zones")

                        for zone_id, base_domain in zones:
                            full_url = base_domain.rstrip("/") + path

                            if zone_id not in zone_batches:
                                zone_batches[zone_id] = set()

                            zone_batches[zone_id].add(full_url)
                            logger.debug(f"Zone {zone_id}: {full_url}")

                        # Check if any batch should be flushed
                        should_flush = any(
                            len(batch) >= batch_size for batch in zone_batches.values()
                        )

                        # Also flush if 5 seconds elapsed
                        if not should_flush and (time.time() - last_flush) >= 5.0:
                            should_flush = True

                        if should_flush:
                            self._flush_all_batches(
                                session, zone_batches, self.settings.api_key
                            )
                            zone_batches.clear()
                            last_flush = time.time()

                    except queue.Empty:
                        # Flush any pending items
                        if zone_batches:
                            self._flush_all_batches(
                                session, zone_batches, self.settings.api_key
                            )
                            zone_batches.clear()
                            last_flush = time.time()

                # Flush remaining items on shutdown
                if zone_batches:
                    self._flush_all_batches(
                        session, zone_batches, self.settings.api_key
                    )

        except Exception:
            logger.exception("Exception in KeyCDN worker thread")

        logger.debug("KeyCDN worker thread terminating")

    def _flush_all_batches(self, session, zone_batches, api_key):
        """Flush all zone batches to KeyCDN API.

        Args:
            session: requests.Session
            zone_batches: Dict {zone_id: set of URLs}
            api_key: KeyCDN API key
        """
        for zone_id, urls in zone_batches.items():
            if not urls:
                continue
            logger.info(f"Flushing {len(urls)} URLs to KeyCDN zone {zone_id}")
            success, data, error = self.purger._purge_batch(
                session, urls, zone_id, api_key
            )

            if not success:
                logger.error(f"Batch purge failed for zone {zone_id}: {error}")


# Singleton instance
KEYCDN_PURGER = KeycdnPurger()


def stopThreads():
    """Cleanup function for tests."""
    KEYCDN_PURGER.stopThreads()
