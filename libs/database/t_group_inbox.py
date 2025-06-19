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
from dimples.utils import CachePool
from dimples.utils import Config
from dimples.database import DbTask, DataCache

from .redis import GroupInboxMessageCache


class MsgTask(DbTask[ID, List[ReliableMessage]]):

    MEM_CACHE_EXPIRES = 360  # seconds
    MEM_CACHE_REFRESH = 128  # seconds

    def __init__(self, receiver: ID, limit: int,
                 redis: GroupInboxMessageCache,
                 mutex_lock: threading.Lock, cache_pool: CachePool):
        super().__init__(mutex_lock=mutex_lock, cache_pool=cache_pool,
                         cache_expires=self.MEM_CACHE_EXPIRES,
                         cache_refresh=self.MEM_CACHE_REFRESH)
        self._receiver = receiver
        self._limit = limit
        self._redis = redis

    @property  # Override
    def cache_key(self) -> ID:
        return self._receiver

    # Override
    async def _read_data(self) -> Optional[List[ReliableMessage]]:
        return await self._redis.get_reliable_messages(receiver=self._receiver, limit=self._limit)

    # Override
    async def _write_data(self, value: List[ReliableMessage]) -> bool:
        pass


class GroupInboxMessageTable(DataCache, ReliableMessageDBI):
    """ Implementations of ReliableMessageDBI """

    def __init__(self, config: Config):
        super().__init__(pool_name='group_inbox')  # ID => List[ReliableMessages]
        self._redis = GroupInboxMessageCache(config=config)

    # noinspection PyMethodMayBeStatic
    def show_info(self):
        print('!!! messages cached in memory only !!!')

    def _new_task(self, receiver: ID, limit: int) -> MsgTask:
        return MsgTask(receiver=receiver, limit=limit,
                       redis=self._redis,
                       mutex_lock=self._mutex_lock, cache_pool=self._cache_pool)

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
        with self.lock:
            # 1. store into redis server
            if await self._redis.save_reliable_message(msg=msg, receiver=receiver):
                # 2. clear cache to reload
                self.cache.erase(key=receiver)
                return True

    # Override
    async def remove_reliable_message(self, msg: ReliableMessage, receiver: ID) -> bool:
        with self.lock:
            # 1. remove from redis server
            if await self._redis.remove_reliable_message(msg=msg, receiver=receiver):
                # 2. clear cache to reload
                self.cache.erase(key=receiver)
                return True
