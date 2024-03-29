#! /usr/bin/env python3
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

"""
    Group bot: 'usher'
    ~~~~~~~~~~~~~~~~~~

    Bot for new members
"""

import sys
import os
from typing import Optional, Union, List

from dimples import DateTime
from dimples import EntityType, ID
from dimples import ReliableMessage
from dimples import ContentType, Content, TextContent
from dimples import ContentProcessor, ContentProcessorCreator
from dimples import CustomizedContent, CustomizedContentProcessor, CustomizedContentHandler
from dimples import BaseContentProcessor
from dimples import TwinsHelper
from dimples import CommonFacebook, CommonMessenger

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from libs.utils import Log, Logging
from libs.utils import Footprint

from libs.client import ClientProcessor, ClientContentProcessorCreator
from libs.client import Emitter, SharedGroupManager

from bots.shared import GlobalVariable
from bots.shared import start_bot


g_vars = {
    'group': None,
    'supervisors': [],
}


class ActiveUsersHandler(TwinsHelper, CustomizedContentHandler, Logging):

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
    def handle_action(self, act: str, sender: ID, content: CustomizedContent, msg: ReliableMessage) -> List[Content]:
        users = content.get('users')
        self.info(msg='received users: %s' % users)
        if not isinstance(users, List):
            self.error(msg='content error: %s, sender: %s' % (content, sender))
            return []
        elif len(users) == 0:
            self.debug(msg='users empty')
            return []
        when = content.time
        if when is None:
            when = DateTime.now()
        elif when < (DateTime.current_timestamp() - 300):
            self.warning(msg='users timeout %s: %s' % (when, users))
            return []
        group = ID.parse(identifier=g_vars.get('group'))
        if group is None:
            self.warning(msg='group ID not set')
            return []
        gm = SharedGroupManager()
        fp = Footprint()
        for item in users:
            identifier = ID.parse(identifier=item.get('U'))
            if identifier is None or identifier.type != EntityType.USER:
                self.warning(msg='ignore user: %s' % item)
                continue
            elif not fp.is_vanished(identifier=identifier, now=when):
                self.info(msg='footprint not vanished yet: %s' % identifier)
                continue
            else:
                fp.touch(identifier=identifier, when=when)
            members = self.facebook.members(identifier=group)
            if members is None or len(members) == 0:
                self.error(msg='group not ready: %s' % group)
                continue
            elif identifier in members:
                self.info(msg='member already exists: %s -> %s' % (identifier, group))
                continue
            self.info(msg='invite %s into group: %s' % (identifier, group))
            gm.invite_members(members=[identifier], group=group)
        return []


class BotTextContentProcessor(BaseContentProcessor, Logging):
    """ Process text content """

    @property
    def facebook(self) -> CommonFacebook:
        barrack = super().facebook
        assert isinstance(barrack, CommonFacebook), 'facebook error: %s' % barrack
        return barrack

    def __get_fullname(self, identifier: ID) -> str:
        facebook = self.facebook
        doc = facebook.document(identifier=identifier)
        name = identifier.name if doc is None else doc.name
        if name is None or len(name) == 0:
            return str(identifier)
        else:
            return '%s (%s)' % (identifier, name)

    @classmethod
    def replace_at(cls, text: str, name: str) -> str:
        at = '@%s' % name
        if text.endswith(at):
            text = text[:-len(at)]
        at = '@%s ' % name
        return text.replace(at, '')

    @classmethod
    def send_text(cls, text: str, receiver: ID, group: Optional[ID]):
        if group is not None:
            receiver = group
        content = TextContent.create(text=text)
        emitter = Emitter()
        emitter.send_content(content=content, receiver=receiver)

    def __query_current_group(self, group: Optional[ID], sender: ID):
        current = g_vars.get('group')
        if isinstance(current, ID):
            name = self.__get_fullname(identifier=current)
            text = 'Current group is "%s" (%s)' % (name, current)
            self.send_text(text=text, receiver=sender, group=group)
            return True
        else:
            text = 'current group not set yet'
            self.send_text(text=text, receiver=sender, group=group)
            return False

    def __set_current_group(self, group: Optional[ID], sender: ID):
        admins = g_vars['supervisors']
        assert isinstance(admins, List), 'supervisors not found: %s' % g_vars
        if group is None:
            text = 'Call me in the group'
            self.send_text(text=text, receiver=sender, group=group)
        elif sender in admins:
            name = self.__get_fullname(identifier=group)
            self.warning(msg='change current group by %s: %s -> %s "%s"' % (sender, g_vars.get('group'), group, name))
            g_vars['group'] = group
            text = 'Current group set to "%s" (%s)' % (name, group)
            self.send_text(text=text, receiver=sender, group=group)
            return True
        else:
            self.warning(msg='permission denied: %s, supervisors: %s' % (sender, admins))
            text = 'permission denied'
            self.send_text(text=text, receiver=sender, group=group)
            return False

    # Override
    def process_content(self, content: Content, r_msg: ReliableMessage) -> List[Content]:
        assert isinstance(content, TextContent), 'text content error: %s' % content
        text = content.text
        if text is None:
            # assert False, 'text content error: %s' % content
            return []
        facebook = self.facebook
        group = content.group
        sender = r_msg.sender
        # if group is None:
        #     nickname = facebook.get_name(identifier=sender)
        #     self.info(msg='ignore message from %s: "%s"' % (nickname, text))
        #     return []
        # check text
        user = facebook.current_user
        assert user is not None, 'failed to get current user'
        nickname = self.facebook.get_name(identifier=user.identifier)
        assert len(nickname) > 0, 'user name error: %s' % user
        naked = self.replace_at(text=text, name=nickname)
        if group is not None and naked == text:
            self.debug(msg='ignore message from %s: "%s"' % (nickname, text))
            return []
        else:
            naked = naked.strip().lower()
        if naked == 'set current group':
            self.__set_current_group(group=group, sender=sender)
        elif naked == 'current group':
            self.__query_current_group(group=group, sender=sender)
        else:
            text = 'Unexpected command: "%s"' % naked
            self.send_text(text=text, receiver=sender, group=group)
        return []


class BotCustomizedContentProcessor(CustomizedContentProcessor, Logging):
    """ Process customized content """

    def __init__(self, facebook, messenger):
        super().__init__(facebook=facebook, messenger=messenger)
        # Module(s) for customized contents
        self.__handler = ActiveUsersHandler(facebook=facebook, messenger=messenger)

    # Override
    def _filter(self, app: str, content: CustomizedContent, msg: ReliableMessage) -> Optional[List[Content]]:
        if app == 'chat.dim.monitor':
            # App ID match
            # return None to fetch module handler
            return None
        # unknown app ID
        return super()._filter(app=app, content=content, msg=msg)

    # Override
    def _fetch(self, mod: str, content: CustomizedContent, msg: ReliableMessage) -> Optional[CustomizedContentHandler]:
        assert mod is not None, 'module name empty: %s' % content
        if mod == 'users':
            # customized module: "users"
            return self.__handler
        # TODO: define your modules here
        # ...
        return super()._fetch(mod=mod, content=content, msg=msg)


class BotContentProcessorCreator(ClientContentProcessorCreator):

    # Override
    def create_content_processor(self, msg_type: Union[int, ContentType]) -> Optional[ContentProcessor]:
        # text
        if msg_type == ContentType.TEXT:
            return BotTextContentProcessor(facebook=self.facebook, messenger=self.messenger)
        # application customized
        if msg_type == ContentType.CUSTOMIZED:
            return BotCustomizedContentProcessor(facebook=self.facebook, messenger=self.messenger)
        # others
        return super().create_content_processor(msg_type=msg_type)


class BotMessageProcessor(ClientProcessor):

    # Override
    def _create_creator(self) -> ContentProcessorCreator:
        return BotContentProcessorCreator(facebook=self.facebook, messenger=self.messenger)


#
# show logs
#
Log.LEVEL = Log.DEVELOP


DEFAULT_CONFIG = '/etc/dimg_bots/config.ini'


if __name__ == '__main__':
    # start group bot
    g_terminal = start_bot(default_config=DEFAULT_CONFIG,
                           app_name='GroupBot: Usher',
                           ans_name='usher',
                           processor_class=BotMessageProcessor)
    shared = GlobalVariable()
    supervisors = shared.config.get_list(section='group', option='supervisors')
    if isinstance(supervisors, List):
        g_vars['supervisors'] = ID.convert(array=supervisors)
