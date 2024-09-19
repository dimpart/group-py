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

from typing import Optional, List, Dict

from dimples import DateTime
from dimples import ID
from dimples import ReliableMessage
from dimples import Envelope, Content
from dimples import CustomizedContent, ReceiptCommand
from dimples import CustomizedContentProcessor
from dimples import CustomizedContentHandler
from dimples import TwinsHelper

from libs.utils import Singleton
from libs.database import Database


class GroupKeyCommand:

    APP = 'chat.dim.group'
    MOD = 'keys'

    @classmethod
    def create(cls, action: str, group: ID, sender: ID, keys: Dict[str, str] = None) -> CustomizedContent:
        app = cls.APP
        mod = cls.MOD
        act = action
        content = CustomizedContent.create(app=app, mod=mod, act=act)
        content.group = group
        content['from'] = str(sender)
        if keys is not None:
            content['keys'] = keys
        return content

    # 1. bot -> sender: 'query'
    # 2. sender -> bot: 'update'
    # 3. member -> bot: 'request'
    # 4. bot -> member: 'respond'

    @classmethod
    def query(cls, group: ID, sender: ID, digest: Optional[str], members: List[ID] = None) -> CustomizedContent:
        """ query group keys from sender """
        content = cls.create(action='query', group=group, sender=sender)
        if digest is not None:
            # current key's digest
            content['keys'] = {
                'digest': digest,
            }
        if members is not None and len(members) > 0:
            # only query for these members
            content['members'] = ID.revert(array=members)
        return content

    @classmethod
    def update(cls, group: ID, sender: ID, keys: Dict[str, str]) -> CustomizedContent:
        """ update group keys from sender """
        if 'time' not in keys:
            keys['time'] = str(DateTime.current_timestamp())
        return cls.create(action='update', group=group, sender=sender, keys=keys)

    @classmethod
    def request(cls, group: ID, sender: ID, digest: Optional[str]) -> CustomizedContent:
        """ request group key for this member """
        content = cls.create(action='query', group=group, sender=sender)
        if digest is not None:
            # current key's digest
            content['keys'] = {
                'digest': digest,
            }
        return content

    @classmethod
    def respond(cls, group: ID, sender: ID, keys: Dict[str, str]) -> CustomizedContent:
        """ respond group key to member """
        return cls.create(action='respond', group=group, sender=sender, keys=keys)


@Singleton
class CustomizedHandler(CustomizedContentHandler):

    def __init__(self):
        super().__init__()
        self.__db: Optional[Database] = None

    @property
    def database(self) -> Optional[Database]:
        return self.__db

    @database.setter
    def database(self, db: Database):
        self.__db = db

    # noinspection PyMethodMayBeStatic
    def _respond_receipt(self, text: str, envelope: Envelope, content: Optional[Content],
                         extra: Optional[Dict] = None) -> List[ReceiptCommand]:
        return [
            # create base receipt command with text, original envelope, serial number & group ID
            TwinsHelper.create_receipt(text=text, envelope=envelope, content=content, extra=extra)
        ]

    async def _update_group_keys(self, group: ID, sender: ID,
                                 content: CustomizedContent, msg: ReliableMessage) -> List[Content]:
        db = self.database
        assert db is not None, 'database not set yet'
        keys = content.get('keys')
        if not isinstance(keys, Dict):
            text = 'Group keys error, failed to update.'
        elif await db.save_group_keys(group=group, sender=sender, keys=keys):
            text = 'Group keys updated.'
        else:
            text = 'Failed to update group keys.'
        # respond
        return self._respond_receipt(text=text, content=content, envelope=msg.envelope)

    async def _query_group_key(self, group: ID, member: ID,
                               content: CustomizedContent, msg: ReliableMessage) -> List[Content]:
        key_sender = ID.parse(identifier=content.get('from'))
        if key_sender is None:
            text = 'Failed to get group keys sender.'
            return self._respond_receipt(text=text, content=content, envelope=msg.envelope)
        else:
            db = self.database
            assert db is not None, 'database not set yet'
            sender = msg.sender
        # get group keys
        keys = await db.get_group_keys(group=group, sender=sender)
        if keys is None:
            keys = {}
        else:
            assert isinstance(keys, Dict), 'group keys error: %s' % keys
        # check group key
        encrypted_key = keys.get(str(member))
        if encrypted_key is None:
            text = 'Failed to get group key.'
            return self._respond_receipt(text=text, content=content, envelope=msg.envelope)
        # build respond
        res = GroupKeyCommand.respond(group=group, sender=sender, keys={
            str(member): encrypted_key,
            'digest': keys.get('digest'),
            'time': keys.get('time'),
        })
        return [res]

    # Override
    async def handle_action(self, act: str, sender: ID,
                            content: CustomizedContent, msg: ReliableMessage) -> List[Content]:
        group = content.group
        if group is None:
            text = 'Group content error.'
            return self._respond_receipt(text=text, content=content, envelope=msg.envelope)
        # app = 'chat.dim.group'
        # mod = 'keys'
        if act == 'update':
            # encrypted group keys from sender:
            # {
            #   '{MEMBER_1}': '{ENCRYPTED_KEY}',
            #   '{MEMBER_2}': '{ENCRYPTED_KEY}',
            #   ...
            #   'digest': '{KEY_DIGEST}'
            # }
            return await self._update_group_keys(group=group, sender=sender, content=content, msg=msg)
        elif act == 'query':
            # load group keys with direction: sender -> group
            # get the encrypted key with member ID
            return await self._query_group_key(group=group, member=sender, content=content, msg=msg)
        else:
            # error
            text = 'Action not supported: %s.' % act
            return self._respond_receipt(text=text, content=content, envelope=msg.envelope)


class CustomizedProcessor(CustomizedContentProcessor):

    # Override
    def _filter(self, app: str, content: CustomizedContent, msg: ReliableMessage) -> Optional[List[Content]]:
        if app == GroupKeyCommand.APP:
            # app == 'chat.dim.group'
            return None
        # not supported
        return super()._filter(app=app, content=content, msg=msg)

    # Override
    def _fetch(self, mod: str, content: CustomizedContent, msg: ReliableMessage) -> Optional[CustomizedContentHandler]:
        if mod == GroupKeyCommand.MOD:
            # mod == 'keys'
            return CustomizedHandler()
        # others
        return super()._fetch(mod=mod, content=content, msg=msg)
