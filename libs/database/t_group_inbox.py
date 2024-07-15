# -*- coding: utf-8 -*-
# ==============================================================================
# MIT License
#
# Copyright (c) 2023 Albert Moky
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

from dimples import ID
from dimples import ReliableMessage
from dimples import ReliableMessageDBI
from dimples.utils import SharedCacheManager
from dimples.utils import CachePool
from dimples.database import DbInfo, DbTask

from .redis import GroupInboxMessageCache


class MsgTask(DbTask):

    MEM_CACHE_EXPIRES = 360  # seconds
    MEM_CACHE_REFRESH = 128  # seconds

    def __init__(self, receiver: ID, limit: int,
                 cache_pool: CachePool, redis: GroupInboxMessageCache,
                 mutex_lock: threading.Lock):
        super().__init__(cache_pool=cache_pool,
                         cache_expires=self.MEM_CACHE_EXPIRES,
                         cache_refresh=self.MEM_CACHE_REFRESH,
                         mutex_lock=mutex_lock)
        self._receiver = receiver
        self._limit = limit
        self._redis = redis

    # Override
    def cache_key(self) -> ID:
        return self._receiver

    # Override
    async def _load_redis_cache(self) -> Optional[List[ReliableMessage]]:
        return await self._redis.get_reliable_messages(receiver=self._receiver, limit=self._limit)

    # Override
    async def _save_redis_cache(self, value: List[ReliableMessage]) -> bool:
        pass

    # Override
    async def _load_local_storage(self) -> Optional[List[ReliableMessage]]:
        pass

    # Override
    async def _save_local_storage(self, value: List[ReliableMessage]) -> bool:
        pass


class GroupInboxMessageTable(ReliableMessageDBI):
    """ Implementations of ReliableMessageDBI """

    def __init__(self, info: DbInfo):
        super().__init__()
        man = SharedCacheManager()
        self._cache = man.get_pool(name='group_inbox')  # ID => List[ReliableMessages]
        self._redis = GroupInboxMessageCache(connector=info.redis_connector)
        self._lock = threading.Lock()

    # noinspection PyMethodMayBeStatic
    def show_info(self):
        print('!!! messages cached in memory only !!!')

    def _new_task(self, receiver: ID, limit: int) -> MsgTask:
        return MsgTask(receiver=receiver, limit=limit,
                       cache_pool=self._cache, redis=self._redis,
                       mutex_lock=self._lock)

    #
    #   ReliableMessageDBI
    #

    # Override
    async def get_reliable_messages(self, receiver: ID, limit: int = 1024) -> List[ReliableMessage]:
        task = self._new_task(receiver=receiver, limit=limit)
        messages = await task.load()
        return [] if messages is None else messages

    # Override
    async def cache_reliable_message(self, msg: ReliableMessage, receiver: ID) -> bool:
        with self._lock:
            # 1. store into redis server
            if await self._redis.save_reliable_message(msg=msg, receiver=receiver):
                # 2. clear cache to reload
                self._cache.erase(key=receiver)
                return True

    # Override
    async def remove_reliable_message(self, msg: ReliableMessage, receiver: ID) -> bool:
        with self._lock:
            # 1. remove from redis server
            if await self._redis.remove_reliable_message(msg=msg, receiver=receiver):
                # 2. clear cache to reload
                self._cache.erase(key=receiver)
                return True
