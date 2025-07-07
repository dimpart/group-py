# -*- coding: utf-8 -*-
#
#   DIMP : Decentralized Instant Messaging Protocol
#
#                                Written in 2024 by Moky <albert.moky@gmail.com>
#
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

from dimples import CustomizedContent


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
            content['members'] = ID.revert(identifiers=members)
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
