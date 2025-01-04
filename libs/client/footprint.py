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
from dimples import CommonFacebook

from ..utils import Singleton
from ..utils import Logging
from ..common import ActiveUser
from ..database import Database


@Singleton
class Footprint(Logging):

    EXPIRES = 36000  # vanished after 10 hours
    INTERVAL = 600   # save interval

    def __init__(self):
        super().__init__()
        self.__facebook: Optional[CommonFacebook] = None
        self.__db: Optional[Database] = None
        self.__active_users: Optional[List[ActiveUser]] = None
        self.__next_time = DateTime.now()  # next time to save

    @property
    def facebook(self) -> Optional[CommonFacebook]:
        return self.__facebook

    @facebook.setter
    def facebook(self, barrack: CommonFacebook):
        self.__facebook = barrack

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
    async def _save_users(self, users: List[ActiveUser], now: DateTime):
        facebook = self.facebook
        assert facebook is not None, 'facebook not set yet'
        users = await _sort_users(users=users, facebook=facebook)
        self.__active_users = users
        if now < self.__next_time:
            self.info(msg='active users not saved now: %d' % len(users))
            return False
        # save to local storage
        self._refresh_next_time(now=now)
        db = self.database
        assert db is not None, 'database not set yet'
        return await db.save_active_users(users=users)

    # private
    async def _load_users(self, now: DateTime) -> List[ActiveUser]:
        # load from local storage
        self._refresh_next_time(now=now)
        db = self.database
        assert db is not None, 'database not set yet'
        return await db.load_active_users()

    async def active_users(self, now: DateTime = None) -> List[ActiveUser]:
        users = self.__active_users
        if users is None:
            if now is None:
                now = DateTime.now()
            users = await self._load_users(now=now)
            self.__active_users = users
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
        if identifier.is_group:
            self.info(msg='ignore group: %s' % identifier)
            return False
        when = await self._check_time(identifier=identifier, when=when)
        if when is None:
            self.warning(msg='time expired: %s' % identifier)
            return False
        # check exist users
        now = DateTime.now()
        users = await self.active_users(now=now)
        found = False
        for item in users:
            if item.identifier == identifier:
                # found, update time and sort
                if not item.touch(when=when):
                    self.info(msg='active user not touch: %s' % item)
                found = True
        if not found:
            # insert new user
            usr = ActiveUser(identifier=identifier, when=when)
            users.insert(0, usr)
        return await self._save_users(users=users, now=now)

    async def is_vanished(self, identifier: ID, now: DateTime = None) -> bool:
        if now is None:
            now = DateTime.now()
        last = await self._last_time(identifier=identifier, now=now)
        return last is None or now > (last + self.EXPIRES)


async def _sort_users(users: List[ActiveUser], facebook: CommonFacebook) -> List[ActiveUser]:
    array = []
    now = DateTime.now()
    users = users.copy()
    for item in users:
        uid = item.identifier
        visa = await facebook.get_visa(user=uid)
        if visa is not None:
            # update with visa time
            last_time = visa.time
            if last_time is not None:
                item.touch(when=last_time)
        # check whether it is gone
        if item.recently_active(now=now):
            array.append(item)
    array.sort(key=lambda x: x.time, reverse=True)
    return array
