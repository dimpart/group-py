# -*- coding: utf-8 -*-
# ==============================================================================
# MIT License
#
# Copyright (c) 2024 Albert Moky
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ==============================================================================

import threading
from typing import List, Optional

from dimples.utils import CachePool
from dimples.utils import Config
from dimples.database import DbTask, DataCache

from ..common.dbi import ActiveUser, ActiveUserDBI
from .dos import ActiveUserStorage


class UsvTask(DbTask[str, List[ActiveUser]]):

    MEM_CACHE_EXPIRES = 36000  # seconds
    MEM_CACHE_REFRESH = 128    # seconds

    def __init__(self, storage: ActiveUserStorage,
                 mutex_lock: threading.Lock, cache_pool: CachePool):
        super().__init__(mutex_lock=mutex_lock, cache_pool=cache_pool,
                         cache_expires=self.MEM_CACHE_EXPIRES,
                         cache_refresh=self.MEM_CACHE_REFRESH)
        self._dos = storage

    @property  # Override
    def cache_key(self) -> str:
        return 'active_users'

    # Override
    async def _read_data(self) -> Optional[List[ActiveUser]]:
        return await self._dos.load_active_users()

    # Override
    async def _write_data(self, value: List[ActiveUser]) -> bool:
        return await self._dos.save_active_users(users=value)


class ActiveUserTable(DataCache, ActiveUserDBI):
    """ Implementations of ActiveUserDBI """

    def __init__(self, config: Config):
        super().__init__(pool_name='dim_network')  # ID => List[ActiveUser]
        self._dos = ActiveUserStorage(config=config)

    def show_info(self):
        self._dos.show_info()

    def _new_task(self) -> UsvTask:
        return UsvTask(storage=self._dos,
                       mutex_lock=self._mutex_lock, cache_pool=self._cache_pool)

    #
    #   ActiveUserDBI
    #

    # Override
    async def save_active_users(self, users: List[ActiveUser]) -> bool:
        task = self._new_task()
        return await task.save(value=users)

    # Override
    async def load_active_users(self) -> List[ActiveUser]:
        task = self._new_task()
        users = await task.load()
        return [] if users is None else users
