from __future__ import annotations
from typing import Optional
from threading import Lock

import multiprocessing
import torch


class SingletonMetaManaged(type):
    """
    Internal metaclass
    The Singleton metaclass for ManagedMemory
    """

    _instance: Optional[ManagedMemory] = None

    def __call__(self) -> ManagedMemory:
        if self._instance is None:
            self._instance = super().__call__()
        return self._instance


class ManagedMemory(metaclass=SingletonMetaManaged):
    """
    ManagedMemory share data structure/database connector that can me access
    from any thread.
    Class property must be resilient to multi-threaded read/write.
    """

    def __init__(self):
        """
        This function must be called on the main thread.
        """
        self.domain_label_map = multiprocessing.Manager().dict()
        self.domain_label_mappers = multiprocessing.Manager().dict()
        self.call_number = multiprocessing.Manager().Value('wait_number', 0)
        self.wait_time = multiprocessing.Manager().Value('wait_time', 0)
        self.wait_mutex = Lock()
        self.metricsmonitor_values = multiprocessing.Manager().dict()
