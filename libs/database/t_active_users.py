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

from dimples.utils import SharedCacheManager
from dimples.utils import CachePool
from dimples.database import DbInfo, DbTask

from ..common.dbi import ActiveUser, ActiveUserDBI
from .dos import ActiveUserStorage


class UsvTask(DbTask):

    MEM_CACHE_EXPIRES = 36000  # seconds
    MEM_CACHE_REFRESH = 128    # seconds

    def __init__(self,
                 cache_pool: CachePool, storage: ActiveUserStorage,
                 mutex_lock: threading.Lock):
        super().__init__(cache_pool=cache_pool,
                         cache_expires=self.MEM_CACHE_EXPIRES,
                         cache_refresh=self.MEM_CACHE_REFRESH,
                         mutex_lock=mutex_lock)
        self._dos = storage

    # Override
    def cache_key(self) -> str:
        return 'active_users'

    # Override
    async def _load_redis_cache(self) -> Optional[List[ActiveUser]]:
        pass

    # Override
    async def _save_redis_cache(self, value: List[ActiveUser]) -> bool:
        pass

    # Override
    async def _load_local_storage(self) -> Optional[List[ActiveUser]]:
        return await self._dos.load_active_users()

    # Override
    async def _save_local_storage(self, value: List[ActiveUser]) -> bool:
        return await self._dos.save_active_users(users=value)


class ActiveUserTable(ActiveUserDBI):
    """ Implementations of ActiveUserDBI """

    def __init__(self, info: DbInfo):
        super().__init__()
        man = SharedCacheManager()
        self._cache = man.get_pool(name='dim_network')  # ID => List[ActiveUser]
        self._dos = ActiveUserStorage(root=info.root_dir, public=info.public_dir, private=info.private_dir)
        self._lock = threading.Lock()

    def show_info(self):
        self._dos.show_info()

    def _new_task(self) -> UsvTask:
        return UsvTask(cache_pool=self._cache, storage=self._dos,
                       mutex_lock=self._lock)

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
