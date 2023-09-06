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
import time
from typing import Optional, Tuple, List

from dimples import ID, ReliableMessage
from dimples import ForwardContent
from dimples import CommonMessenger

from ..utils import Singleton, Runner, Logging
from ..database import Database


@Singleton
class Footprint:

    EXPIRES = 36000  # vanished after 10 hours

    def __init__(self):
        super().__init__()
        self.__active_times = {}  # ID => float

    def __get_time(self, identifier: ID, when: Optional[float]) -> Optional[float]:
        now = time.time()
        if when is None or when <= 0 or when >= now:
            return now
        elif when > self.__active_times.get(identifier, 0):
            return when
        # else:
        #     # time expired, drop it
        #     return None

    def touch(self, identifier: ID, when: float = None):
        when = self.__get_time(identifier=identifier, when=when)
        if when is not None:
            self.__active_times[identifier] = when
            return True

    def is_vanished(self, identifier: ID, now: float = None) -> bool:
        last_time = self.__active_times.get(identifier)
        if last_time is None:
            return True
        if now is None:
            now = time.time()
        return now > (last_time + self.EXPIRES)


@Singleton
class Distributor:

    def __init__(self):
        super().__init__()
        self.__messenger = None
        self.__footprint = Footprint()

    @property
    def footprint(self) -> Footprint:
        return self.__footprint

    @property
    def messenger(self) -> CommonMessenger:
        return self.__messenger

    @property
    def database(self) -> Database:
        messenger = self.messenger
        assert messenger is not None, 'messenger not set yet'
        db = messenger.database
        assert isinstance(db, Database), 'database error: %s' % db
        return db

    @messenger.setter
    def messenger(self, transceiver: CommonMessenger):
        self.__messenger = transceiver

    def forward_message(self, msg: ReliableMessage, receiver: ID):
        content = ForwardContent.create(message=msg)
        self.messenger.send_content(sender=None, receiver=receiver, content=content, priority=1)

    def __deliver(self, msg: ReliableMessage, receiver: ID):
        if self.footprint.is_vanished(identifier=receiver):
            # the receiver isn't present recently, store this message to inbox
            self.database.inbox_cache_reliable_message(msg=msg, receiver=receiver)
        else:
            self.forward_message(msg=msg, receiver=receiver)

    def deliver(self, msg: ReliableMessage, group: ID, recipients: List[ID]) -> Tuple[List[ID], List[ID]]:
        db = self.database
        # 0. check receiver
        receiver = msg.receiver
        if receiver.is_broadcast:
            # broadcast message has no encrypted key, so
            # just deliver it directly here.
            for item in recipients:
                self.__deliver(msg=msg, receiver=item)
            return recipients, []
        # 1. check keys for encrypted message
        sender = msg.sender
        keys = msg.encrypted_keys
        if keys is not None:
            db.save_group_keys(group=group, sender=sender, keys=keys)
        keys = db.group_keys(group=group, sender=sender)
        if keys is None:
            # keys not found, cannot deliver message
            return [], recipients
        # 2. try to deliver one by one
        success = []
        missing = []
        for item in recipients:
            encrypted_key = keys.get(str(item))
            if encrypted_key is None:
                missing.append(item)
                continue
            # create new message for this member
            info = msg.copy_dictionary()
            info.pop('keys', None)
            info['key'] = encrypted_key
            info['group'] = str(group)
            info['receiver'] = str(item)
            r_msg = ReliableMessage.parse(msg=info)
            if r_msg is None:
                # should not happen
                continue
            self.__deliver(msg=r_msg, receiver=item)
            success.append(item)
        # OK
        return success, missing


@Singleton
class Receptionist(Runner, Logging):

    def __init__(self):
        super().__init__(interval=Runner.INTERVAL_SLOW)
        self.__distributor = Distributor()
        self.__users = []
        self.__lock = threading.Lock()

    @property
    def distributor(self) -> Distributor:
        return self.__distributor

    @property
    def footprint(self) -> Footprint:
        return self.__distributor.footprint

    @property
    def messenger(self) -> CommonMessenger:
        return self.__distributor.messenger

    @messenger.setter
    def messenger(self, transceiver: CommonMessenger):
        self.__distributor.messenger = transceiver

    def touch(self, identifier: ID, when: float = None):
        fp = self.footprint
        vanished = fp.is_vanished(identifier=identifier)
        touched = fp.touch(identifier=identifier, when=when)
        if vanished and touched:
            with self.__lock:
                self.__users.append(identifier)

    def next_user(self) -> Optional[ID]:
        with self.__lock:
            if len(self.__users) > 0:
                return self.__users.pop(0)

    # Override
    def process(self) -> bool:
        user = self.next_user()
        if user is None:
            # nothing to do now, return false to have a rest
            return False
        distributor = self.__distributor
        db = distributor.database
        try:
            messages = db.inbox_reliable_messages(receiver=user)
            self.info(msg='forwarding %d message(s) for user: %s' % (len(messages), user))
            for msg in messages:
                distributor.forward_message(msg=msg, receiver=user)
        except Exception as error:
            self.error(msg='failed to forward message: %s' % error)
            return False

    def start(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
