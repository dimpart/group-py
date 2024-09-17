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

from typing import Optional, List

from dimples import DateTime
from dimples import ID

from libs.utils import Singleton
from libs.common import ActiveUser
from libs.database import Database


@Singleton
class Footprint:

    EXPIRES = 36000  # vanished after 10 hours
    INTERVAL = 600   # save interval

    def __init__(self):
        super().__init__()
        self.__db: Optional[Database] = None
        self.__active_users: Optional[List[ActiveUser]] = None
        self.__next_time = DateTime.now()  # next time to save

    @property
    def database(self) -> Optional[Database]:
        return self.__db

    @database.setter
    def database(self, db: Database):
        self.__db = db

    # private
    def _refresh_next_time(self, now: DateTime):
        next_time = now + self.INTERVAL
        self.__next_time = DateTime(timestamp=next_time)

    # private
    async def _sort_users(self, users: List[ActiveUser], now: DateTime) -> bool:
        users.sort(key=lambda x: x.time, reverse=True)
        if now > self.__next_time:
            return await self._save_users(users=users, now=now)

    # private
    async def _save_users(self, users: List[ActiveUser], now: DateTime):
        db = self.database
        assert db is not None, 'database not set yet'
        self._refresh_next_time(now=now)
        self.__active_users = users
        return await db.save_active_users(users=users)

    # private
    async def _load_users(self, now: DateTime) -> List[ActiveUser]:
        db = self.database
        assert db is not None, 'database not set yet'
        self._refresh_next_time(now=now)
        users = await db.load_active_users()
        self.__active_users = users
        return users

    async def active_users(self, now: DateTime = None) -> List[ActiveUser]:
        users = self.__active_users
        if users is None:
            if now is None:
                now = DateTime.now()
            users = await self._load_users(now=now)
        return users

    # private
    async def _last_time(self, identifier: ID, now: DateTime) -> Optional[DateTime]:
        users = await self.active_users(now=now)
        for item in users:
            if item.identifier == identifier:
                return item.time

    # private
    async def _check_time(self, identifier: ID, when: Optional[DateTime]) -> Optional[DateTime]:
        now = DateTime.now()
        if when is None or when <= 0 or when >= now:
            return now
        last = await self._last_time(identifier=identifier, now=now)
        if last is None or last < when:
            return when
        # else:
        #     # time expired, drop it
        #     return None

    async def touch(self, identifier: ID, when: DateTime = None):
        when = await self._check_time(identifier=identifier, when=when)
        if when is None:
            return False
        # check exist users
        now = DateTime.now()
        users = await self.active_users(now=now)
        for item in users:
            if item.identifier == identifier:
                # found, update time and sort
                if item.touch(when=when):
                    return await self._sort_users(users=users, now=now)
                return False
        # insert new user
        usr = ActiveUser(identifier=identifier, when=when)
        users.insert(0, usr)
        return await self._save_users(users=users, now=now)

    async def is_vanished(self, identifier: ID, now: DateTime = None) -> bool:
        if now is None:
            now = DateTime.now()
        last = await self._last_time(identifier=identifier, now=now)
        return last is None or now > (last + self.EXPIRES)
