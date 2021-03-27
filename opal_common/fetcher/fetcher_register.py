from opal_common.fetcher.logger import get_logger
from typing import Type, Optional, Dict
from .fetch_provider import BaseFetchProvider
from .providers.http_get_fetch_provider import HttpGetFetchProvider
from .events import FetchEvent
from ..config import FETCH_PROVIDER_MODULES

logger = get_logger("opal.fetcher_register")

class FetcherRegisterException(Exception):
    pass


class NoMatchingFetchProviderException(FetcherRegisterException):
    pass


class FetcherRegister:
    """
    A store for fetcher providers
    """

    # Builtin fetchers
    BASIC_CONFIG = {
        "HttpGetFetchProvider": HttpGetFetchProvider,
    }

    def __init__(self, config: Optional[Dict[str, BaseFetchProvider]] = None) -> None:
        if config is not None:
            self._config = config
        else:
            from ..emport import emport_objects_by_class
            # load fetchers
            fetchers = []
            for module_path in FETCH_PROVIDER_MODULES:
                try:
                    fetchers.extend(emport_objects_by_class(module_path, BaseFetchProvider, ["*"]))
                except:
                    logger.exception("Failed to load FetchingProvider module - {module_path}", module_path=module_path)
            self._config = {name: fetcher for name,fetcher in fetchers}
        logger.info("Fetcher Register loaded", extra={'config': self._config})

    def register_fetcher(self, name: str, fetcher_class: Type[BaseFetchProvider]):
        self._config[name] = fetcher_class

    def get_fetcher(self, name: str, event: FetchEvent) -> BaseFetchProvider:
        """
        Init a fetcher instance from a registered fetcher class name

        Args:
            name (str): Name of a registered fetcher
            event (FetchEvent): Event used to configure the fetcher

        Returns:
            BaseFetchProvider: A fetcher instance
        """
        provider_class = self._config.get(name, None)
        if provider_class is None:
            raise NoMatchingFetchProviderException(f"Couldn't find a match for - {name} , {event}")
        fetcher = provider_class(event)
        if event.retry is not None:
            fetcher.set_retry_config(event.retry)
        return fetcher

    def get_fetcher_for_event(self, event: FetchEvent) -> BaseFetchProvider:
        """
        Same as get_fetcher, using the event information to deduce the fetcher class

        Args:
            event (FetchEvent): Event used to choose and configure the fetcher

        Returns:
            BaseFetchProvider: A fetcher instance
        """
        return self.get_fetcher(event.fetcher, event)
