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

import time
from typing import Optional

from dimples import ID, ReliableMessage
from dimples import CommonFacebook, CommonMessenger

from ..utils import Singleton, Logging
from ..database import Database


@Singleton
class Footprint:

    EXPIRES = 36000  # vanished after 10 hours

    def __init__(self):
        super().__init__()
        self.__active_times = {}  # ID => float

    def __get_time(self, identifier: ID, now: Optional[float]) -> Optional[float]:
        current = time.time()
        if now is None or now <= 0 or now >= current:
            return current
        elif now > self.__active_times.get(identifier, 0):
            return now
        # else:
        #     # time expired, drop it
        #     return None

    def touch(self, identifier: ID, now: float = None):
        now = self.__get_time(identifier=identifier, now=now)
        if now is not None:
            self.__active_times[identifier] = now
            return True

    def is_vanished(self, identifier: ID, now: float = None) -> bool:
        last_time = self.__active_times.get(identifier)
        if last_time is None:
            return True
        if now is None:
            now = time.time()
        return now > (last_time + self.EXPIRES)


@Singleton
class Distributor(Logging):

    def __init__(self):
        super().__init__()
        self.__database = None
        self.__facebook = None
        self.__messenger = None

    @property
    def database(self) -> Database:
        return self.__database

    @database.setter
    def database(self, db: Database):
        self.__database = db

    @property
    def facebook(self) -> CommonFacebook:
        return self.__facebook

    @facebook.setter
    def facebook(self, barrack: CommonFacebook):
        self.__facebook = barrack

    @property
    def messenger(self) -> CommonMessenger:
        return self.__messenger

    @messenger.setter
    def messenger(self, transceiver: CommonMessenger):
        self.__messenger = transceiver

    def deliver(self, receiver: ID, msg: ReliableMessage) -> bool:
        pass
