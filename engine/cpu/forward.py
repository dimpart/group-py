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
from typing import Optional, Set, List, Dict

from dimples import ID, ReliableMessage
from dimples import Content, ForwardContent
from dimples import BaseContentProcessor
from dimples import CommonFacebook, CommonMessenger
from dimples import TwinsHelper

from libs.utils import Singleton
from libs.utils import Runner
from libs.utils import Logging
from libs.common import GroupKeyCommand
from libs.database import Database
from libs.client import Footprint


@Singleton
class GroupMessageDistributor(Runner, Logging):

    def __init__(self):
        super().__init__(interval=Runner.INTERVAL_SLOW)
        self.__db: Optional[Database] = None
        self.__messenger: Optional[CommonMessenger] = None
        # waiting members
        self.__members: Set[ID] = set()
        self.__lock = threading.Lock()
        # Runner.async_task(coro=self.start())
        Runner.thread_run(runner=self)

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
        with self.__lock:
            db = self.database
            await db.inbox_cache_reliable_message(msg=msg, receiver=receiver)
            self.__members.add(receiver)

    def _get_users(self) -> Optional[Set[ID]]:
        with self.__lock:
            if len(self.__members) > 0:
                users = self.__members
                self.__members = set()
                return users

    # Override
    async def process(self) -> bool:
        database = self.database
        messenger = self.messenger
        if database is None or messenger is None:
            self.warning(msg='group message distributor not ready yet')
            return False
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
        db = self.database
        messenger = self.messenger
        for receiver in recipients:
            if await fp.is_vanished(identifier=receiver):
                self.info(msg='user %s is vanished, ignore it' % receiver)
                continue
            messages = await db.inbox_reliable_messages(receiver=receiver)
            for msg in messages:
                command = ForwardContent.create(message=msg)
                await messenger.send_content(sender=None, receiver=receiver, content=command)
            # TODO: load all messages?


@Singleton
class GroupMessageHandler(Runner, Logging):

    def __init__(self):
        super().__init__(interval=Runner.INTERVAL_SLOW)
        self.__db: Optional[Database] = None
        self.__facebook: Optional[CommonFacebook] = None
        self.__messenger: Optional[CommonMessenger] = None
        # message queue
        self.__messages: List[ReliableMessage] = []
        self.__lock = threading.Lock()
        # Runner.async_task(coro=self.start())
        Runner.thread_run(runner=self)

    @property
    def database(self) -> Optional[Database]:
        return self.__db

    @database.setter
    def database(self, db: Database):
        self.__db = db

    @property
    def facebook(self) -> Optional[CommonFacebook]:
        return self.__facebook

    @facebook.setter
    def facebook(self, barrack: CommonFacebook):
        self.__facebook = barrack

    @property
    def messenger(self) -> Optional[CommonMessenger]:
        return self.__messenger

    @messenger.setter
    def messenger(self, transceiver: CommonMessenger):
        self.__messenger = transceiver

    async def _send_content(self, content: Content, receiver: ID, priority: int = 0):
        messenger = self.messenger
        i_msg, r_msg = await messenger.send_content(sender=None, receiver=receiver, content=content, priority=priority)
        return r_msg is not None

    async def _fetch_group_keys(self, group: ID, sender: ID, keys: Dict[str, str]) -> Optional[Dict[str, str]]:
        db = self.database
        if keys is not None and len(keys) > 0:
            await db.save_group_keys(group=group, sender=sender, keys=keys)
        # get newest keys
        return await db.get_group_keys(group=group, sender=sender)

    def append_message(self, msg: ReliableMessage):
        """ Add group message to waiting queue """
        with self.__lock:
            self.__messages.append(msg)

    def next_message(self) -> Optional[ReliableMessage]:
        with self.__lock:
            if len(self.__messages) > 0:
                return self.__messages.pop(0)

    # Override
    async def process(self) -> bool:
        database = self.database
        facebook = self.facebook
        messenger = self.messenger
        if database is None or facebook is None or messenger is None:
            self.warning(msg='group message handler not ready yet')
            return False
        msg = self.next_message()
        if msg is None:
            return False
        else:
            receiver = msg.receiver
            group = msg.group
        try:
            if receiver.is_group:
                # group message
                await self._split_group_message(group=receiver, msg=msg)
            elif receiver.is_broadcast and group is not None:
                # group command
                await self._process_group_command(group=group, msg=msg)
            else:
                self.error(msg='group message error: %s (%s) %s' % (receiver, group, msg))
            return True
        except Exception as error:
            self.error(msg='failed to process message: %s => %s: %s' % (msg.sender, receiver, error))
            return False

    #
    #   Group Message
    #

    async def _split_group_message(self, group: ID, msg: ReliableMessage):
        if group.is_broadcast:
            self.error(msg='group error: %s' % group)
            return False
        else:
            # update encrypted keys
            sender = msg.sender
            encrypted_keys = await self._fetch_group_keys(group=group, sender=sender, keys=msg.encrypted_keys)
            if encrypted_keys is None:
                return False
        # 0. check permission
        all_members = await self.facebook.get_members(identifier=group)
        # TODO: check owner, administrators
        if sender not in all_members:
            text = 'Permission denied.'
            receipt = TwinsHelper.create_receipt(text=text, envelope=msg.envelope, content=None, extra=None)
            receipt.group = group
            await self._send_content(content=receipt, receiver=sender, priority=1)
            return False
        else:
            other_members = set(all_members)
            other_members.discard(sender)
        # 1. split for other members
        distributor = GroupMessageDistributor()
        group_str = str(group)
        missed = set()
        for member in other_members:
            # get encrypt key with target receiver
            target = str(member)
            enc_key = encrypted_keys.get(target)
            if enc_key is None:
                missed.add(member)
                continue
            else:
                self.info(msg='split group message: %s => %s (%s)' % (sender, member, group))
            # forward message
            info = msg.copy_dictionary()
            info.pop('keys', None)
            info['key'] = enc_key
            info['receiver'] = target
            info['group'] = group_str
            # content = ForwardContent.create()
            # content['forward'] = info
            # await self._send_content(content=content, receiver=member)
            await distributor.cache_message(msg=ReliableMessage.parse(msg=info), receiver=member)
        # 2. query missed keys
        key_digest = encrypted_keys.get('digest')
        if key_digest is not None and len(missed) > 0:
            self.warning(msg='query missed group keys: %s => %s, %s' % (sender, group, missed))
            query = GroupKeyCommand.query(group=group, sender=sender, digest=key_digest, members=list(missed))
            await self._send_content(content=query, receiver=sender, priority=1)
        # TODO: 3. respond receipt
        return True

    #
    #   Group Command
    #

    async def _process_group_command(self, group: ID, msg: ReliableMessage):
        if group.is_broadcast:
            self.error(msg='group error: %s' % group)
            return False
        messenger = self.messenger
        responses = await messenger.process_reliable_message(msg=msg)
        for res in responses:
            await messenger.send_reliable_message(msg=res)
        # TODO: forward group command to other members?
        return True


class ForwardContentProcessor(BaseContentProcessor):
    """
        Forward Content Processor
        ~~~~~~~~~~~~~~~~~~~~~~~~~

    """

    @property
    def facebook(self) -> CommonFacebook:
        barrack = super().facebook
        assert isinstance(barrack, CommonFacebook), 'facebook error: %s' % barrack
        return barrack

    @property
    def messenger(self) -> CommonMessenger:
        transceiver = super().messenger
        assert isinstance(transceiver, CommonMessenger), 'messenger error: %s' % transceiver
        return transceiver

    # Override
    async def process_content(self, content: Content, r_msg: ReliableMessage) -> List[Content]:
        assert isinstance(content, ForwardContent), 'forward content error: %s' % content
        secrets = content.secrets
        messenger = self.messenger
        handler = GroupMessageHandler()
        fp = Footprint()
        await fp.touch(identifier=r_msg.sender, when=r_msg.time)
        responses = []
        for item in secrets:
            await fp.touch(identifier=item.sender, when=item.time)
            receiver = item.receiver
            group = item.group
            if receiver.is_group:
                # group message
                assert not receiver.is_broadcast, 'message error: %s => %s' % (item.sender, receiver)
                handler.append_message(msg=item)
                results = []
            elif receiver.is_broadcast and group is not None:
                # group command
                assert not group.is_broadcast, 'message error: %s => %s (%s)' % (item.sender, receiver, group)
                handler.append_message(msg=item)
                results = []
            else:
                results = await messenger.process_reliable_message(msg=item)
            # NOTICE: append one result for each forwarded message.
            if len(results) == 1:
                res = ForwardContent.create(message=results[0])
            else:
                res = ForwardContent.create(messages=results)
            responses.append(res)
        return responses
