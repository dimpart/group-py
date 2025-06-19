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
from typing import Optional, Tuple, Dict

from dimples import ID

from dimples.utils import CachePool
from dimples.common import GroupKeysDBI
from dimples.database import GroupKeysStorage
from dimples.database import GroupKeysCache
from dimples.utils import Config
from dimples.database import DbTask, DataCache


class PwdTask(DbTask[Tuple[ID, ID], Dict[str, str]]):

    def __init__(self, group: ID, sender: ID,
                 redis: GroupKeysCache, storage: GroupKeysStorage,
                 mutex_lock: threading.Lock, cache_pool: CachePool):
        super().__init__(mutex_lock=mutex_lock, cache_pool=cache_pool)
        self._group = group
        self._sender = sender
        self._redis = redis
        self._dos = storage

    @property  # Override
    def cache_key(self) -> Tuple[ID, ID]:
        return self._group, self._sender

    # Override
    async def _read_data(self) -> Optional[Dict[str, str]]:
        # 1. the redis server will return None when cache not found
        # 2. when redis server return an empty array, no need to check local storage again
        keys = await self._redis.get_group_keys(group=self._group, sender=self._sender)
        if keys is not None:
            return keys
        # 3. the local storage will return None when file not found
        keys = await self._dos.get_group_keys(group=self._group, sender=self._sender)
        if keys is None:
            # 4. return empty dictionary as a placeholder for the memory cache
            keys = {}
        # 5. update redis server
        await self._redis.save_group_keys(group=self._group, sender=self._sender, keys=keys)
        return keys

    # Override
    async def _write_data(self, value: Dict[str, str]) -> bool:
        # 1. store into redis server
        ok1 = await self._redis.save_group_keys(group=self._group, sender=self._sender, keys=value)
        # 2. save into local storage
        ok2 = await self._dos.save_group_keys(group=self._group, sender=self._sender, keys=value)
        return ok1 or ok2


class GroupKeysTable(DataCache, GroupKeysDBI):
    """ Implementations of GroupKeysDBI """

    def __init__(self, config: Config):
        super().__init__(pool_name='group.keys')  # (ID, ID) => Dict
        self._redis = GroupKeysCache(config=config)
        self._dos = GroupKeysStorage(config=config)

    def show_info(self):
        self._dos.show_info()

    def _new_task(self, group: ID, sender: ID) -> PwdTask:
        return PwdTask(group=group, sender=sender,
                       redis=self._redis, storage=self._dos,
                       mutex_lock=self._mutex_lock, cache_pool=self._cache_pool)

    async def _merge_keys(self, group: ID, sender: ID, keys: Dict[str, str]) -> Optional[Dict[str, str]]:
        # 0. load old records
        table = await self.get_group_keys(group=group, sender=sender)
        if table is None:
            # new keys
            return keys
        # 1. check times
        old_time = table.get('time')
        new_time = keys.get('time')
        # assert old_time is not None and new_time is not None
        if old_time is not None:
            if new_time is None:
                # error
                return None
            elif float(new_time) < float(old_time):
                # expired records, drop them
                return None
        # 2. check digest
        old_digest = table.get('digest')
        new_digest = keys.get('digest')
        if old_digest is None or new_digest is None:
            # FIXME: old version?
            return keys
        elif old_digest != new_digest:
            # key changed
            return keys
        # 3. same digest, merge keys
        table = table.copy()
        for member in keys:
            # update key for member
            table[member] = keys[member]
        # table['digest'] = new_digest
        # table['time'] = new_time
        return table

    #
    #   Group Keys DBI
    #

    # Override
    async def save_group_keys(self, group: ID, sender: ID, keys: Dict[str, str]) -> bool:
        keys = await self._merge_keys(group=group, sender=sender, keys=keys)
        if keys is None:
            return False
        task = self._new_task(group=group, sender=sender)
        return await task.save(value=keys)

    # Override
    async def get_group_keys(self, group: ID, sender: ID) -> Optional[Dict[str, str]]:
        task = self._new_task(group=group, sender=sender)
        return await task.load()
