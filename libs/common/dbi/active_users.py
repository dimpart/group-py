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

from abc import ABC, abstractmethod
from typing import Any, List, Dict

from dimples import DateTime
from dimples import ID


class ActiveUser:

    MONTHLY = 3600 * 24 * 30

    def __init__(self, identifier: ID, when: DateTime):
        super().__init__()
        self.__identifier = identifier
        self.__time = when

    @property
    def identifier(self) -> ID:
        return self.__identifier

    @property
    def time(self) -> DateTime:
        return self.__time

    def touch(self, when: DateTime) -> bool:
        assert when is not None, 'active time should not empty'
        if self.__time < when:
            self.__time = when
            return True
        else:
            return False

    def recently_active(self, now: DateTime) -> bool:
        return now < (self.__time + self.MONTHLY)

    #
    #   Factories
    #

    @classmethod
    def parse(cls, user: Any):  # -> Optional[ActiveUser]:
        if user is None:
            return None
        elif isinstance(user, ActiveUser):
            return user
        else:
            assert isinstance(user, Dict), 'active user error: %s' % user
        identifier = ID.parse(user.get('ID'))
        when = DateTime.parse(user.get('time'))
        if identifier is None or when is None:
            # assert False, 'active user error: %s' % user
            return None
        return ActiveUser(identifier=identifier, when=when)

    @classmethod
    def convert(cls, array: List[Dict]):  # -> List[ActiveUser]:
        users = []
        for item in array:
            usr = cls.parse(user=item)
            if usr is not None:
                users.append(usr)
        return users

    @classmethod
    def revert(cls, array) -> List[Dict]:
        users = []
        for item in array:
            if isinstance(item, ActiveUser):
                info = {
                    'ID': str(item.identifier),
                    'time': float(item.time),
                    'time_str': str(item.time),
                }
            elif isinstance(item, Dict):
                assert 'ID' in item and 'time' in item, 'user info error: %s' % item
                info = item
            else:
                assert False, 'user info error: %s' % item
            users.append(info)
        return users


class ActiveUserDBI(ABC):

    @abstractmethod
    async def save_active_users(self, users: List[ActiveUser]) -> bool:
        raise NotImplemented

    @abstractmethod
    async def load_active_users(self) -> List[ActiveUser]:
        raise NotImplemented
