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
from typing import Optional, Set, List, Dict

from dimples import ID, ReliableMessage
from dimples import ForwardContent
from dimples import CommonMessenger

from libs.utils import Singleton
from libs.utils import Runner
from libs.utils import Logging
from libs.database import Database
from libs.client import Footprint


@Singleton
class GroupMessageDistributor(Runner, Logging):

    def __init__(self):
        super().__init__(interval=Runner.INTERVAL_SLOW)
        self.__db: Optional[Database] = None
        self.__messenger: Optional[CommonMessenger] = None
        # waiting queue
        self.__message_cache: Dict[ID, List[ReliableMessage]] = {}
        self.__members: Set[ID] = set()
        self.__lock = threading.Lock()
        # auto start
        self.start()

    @property
    def database(self) -> Optional[Database]:
        return self.__db

    @database.setter
    def database(self, db: Database):
        self.__db = db

    @property
    def messenger(self) -> CommonMessenger:
        return self.__messenger

    @messenger.setter
    def messenger(self, transceiver: CommonMessenger):
        self.__messenger = transceiver

    async def cache_message(self, msg: ReliableMessage, receiver: ID):
        fp = Footprint()
        db = self.database
        with self.__lock:
            if await fp.is_vanished(identifier=receiver):
                self.info(msg='store message for vanished receiver: %s' % receiver)
                await db.inbox_cache_reliable_message(msg=msg, receiver=receiver)
            else:
                messages = self.__message_cache.get(receiver)
                if messages is None:
                    messages = []
                    self.__message_cache[receiver] = messages
                messages.append(msg)
                self.__members.add(receiver)
        return True

    async def _get_messages(self, receiver: ID) -> List[ReliableMessage]:
        db = self.database
        with self.__lock:
            messages = self.__message_cache.get(receiver)
            stored = await db.inbox_reliable_messages(receiver=receiver)
            if messages is None or len(messages) == 0:
                return stored
            elif len(stored) == 0:
                return messages
            else:
                return messages + stored

    def wakeup_user(self, identifier: ID):
        with self.__lock:
            self.__members.add(identifier)

    def _get_users(self) -> Optional[Set[ID]]:
        with self.__lock:
            if len(self.__members) > 0:
                users = self.__members
                self.__members = set()
                return users

    def start(self):
        thr = Runner.async_thread(coro=self.run())
        thr.start()

    # Override
    async def process(self) -> bool:
        # get waiting users
        members = self._get_users()
        if members is None:
            return False
        try:
            await self._check_users(recipients=members)
            return True
        except Exception as error:
            self.error(msg='failed to distribute group message for %s: %s' % (members, error))
            return False

    async def _check_users(self, recipients: Set[ID]):
        self.info(msg='checking message for users: %s' % recipients)
        fp = Footprint()
        messenger = self.messenger
        for receiver in recipients:
            if await fp.is_vanished(identifier=receiver):
                self.info(msg='user %s is vanished, ignore it' % receiver)
                continue
            messages = await self._get_messages(receiver=receiver)
            self.info(msg='forward %d messages for receiver: %s' % (len(messages), receiver))
            for msg in messages:
                command = ForwardContent.create(message=msg)
                await messenger.send_content(sender=None, receiver=receiver, content=command)
            # TODO: load all messages?
