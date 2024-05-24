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
from typing import Optional, List

from dimples import EntityType, ID
from dimples import Content, TextContent
from dimples import CommonFacebook

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from libs.utils import Log, Runner

from libs.chat import Greeting, ChatRequest
from libs.chat import ChatBox, ChatClient

from libs.client import ClientProcessor
from libs.client import SharedGroupManager
from libs.client import Emitter

from bots.shared import GlobalVariable
from bots.shared import start_bot


g_vars = {
    'group': None,
    'supervisors': [],
}


class GroupChatBox(ChatBox):

    # build group info
    async def __group_info(self, group: ID) -> str:
        facebook = self.facebook
        doc = await facebook.get_document(identifier=group)
        name = group.name if doc is None else doc.name
        # name = md_esc(text=name)
        return '- Name: ***"%s"***\n- ID  : %s\n' % (name, group)

    async def __query_current_group(self, request: ChatRequest):
        current = g_vars.get('group')
        if isinstance(current, ID):
            text = 'Current group is:\n%s' % await self.__group_info(group=current)
            await self.respond_markdown(text=text, request=request)
            return True
        else:
            text = 'current group not set yet'
            await self.respond_text(text=text, request=request)
            return False

    async def __set_current_group(self, request: ChatRequest):
        sender = request.envelope.sender
        group = request.content.group
        admins = g_vars['supervisors']
        assert isinstance(admins, List), 'supervisors not found: %s' % g_vars
        if group is None:
            text = 'Call me in the group'
            await self.respond_text(text=text, request=request)
        elif sender in admins:
            old = g_vars.get('group')
            self.warning(msg='change current group by %s: %s -> %s' % (sender, old, group))
            g_vars['group'] = group
            text = 'Current group set to:\n%s' % await self.__group_info(group=group)
            if old is not None:
                assert isinstance(old, ID), 'old group ID error: %s' % old
                text += '\n'
                text += 'replacing the old one:\n%s' % await self.__group_info(group=old)
            await self.respond_markdown(text=text, request=request)
            return True
        else:
            self.warning(msg='permission denied: %s, supervisors: %s' % (sender, admins))
            text = 'permission denied'
            await self.respond_text(text=text, request=request)
            return False

    # Override
    async def _ask_question(self, prompt: str, content: TextContent, request: ChatRequest) -> bool:
        command = prompt.strip().lower()
        # group commands
        if command == 'set current group':
            return await self.__set_current_group(request=request)
        elif command == 'current group':
            return await self.__query_current_group(request=request)
        else:
            text = 'Unexpected command: "%s"' % command
            await self.respond_text(text=text, request=request)

    # Override
    async def _say_hi(self, prompt: str, request: Greeting) -> bool:
        # check current group
        group = ID.parse(identifier=g_vars.get('group'))
        if group is None:
            self.warning(msg='group ID not set')
            return False
        # check members
        members = await self.facebook.get_members(identifier=group)
        if members is None or len(members) == 0:
            self.error(msg='group not ready: %s' % group)
            return False
        identifier = request.identifier
        assert identifier.type == EntityType.USER, 'user error: %s' % identifier
        if identifier in members:
            self.info(msg='member already exists: %s -> %s' % (identifier, group))
            return False
        self.info(msg='invite %s into group: %s' % (identifier, group))
        gm = SharedGroupManager()
        return await gm.invite_members(members=[identifier], group=group)

    # Override
    async def _send_content(self, content: Content, receiver: ID) -> bool:
        emitter = Emitter()
        await emitter.send_content(content=content, receiver=receiver)
        return True


class GroupChatClient(ChatClient):

    def __init__(self, facebook: CommonFacebook):
        super().__init__()
        self.__facebook = facebook

    # Override
    def _new_box(self, identifier: ID) -> Optional[ChatBox]:
        facebook = self.__facebook
        return GroupChatBox(identifier=identifier, facebook=facebook)


class BotMessageProcessor(ClientProcessor):

    # Override
    def _create_chat_client(self) -> ChatClient:
        client = GroupChatClient(facebook=self.facebook)
        # Runner.async_task(coro=client.start())
        Runner.thread_run(runner=client)
        return client


#
# show logs
#
Log.LEVEL = Log.DEVELOP


DEFAULT_CONFIG = '/etc/dim_bots/config.ini'


ChatBox.EXPIRES = 36000  # vanished after 10 hours


async def main():
    # create & start bot
    client = await start_bot(default_config=DEFAULT_CONFIG,
                             app_name='GroupBot: Usher',
                             ans_name='usher',
                             processor_class=BotMessageProcessor)
    # set supervisors
    shared = GlobalVariable()
    supervisors = shared.config.get_list(section='group', option='supervisors')
    if isinstance(supervisors, List):
        g_vars['supervisors'] = ID.convert(array=supervisors)
    # main run loop
    while True:
        await Runner.sleep(seconds=1.0)
        if not client.running:
            break
    Log.warning(msg='bot stopped: %s' % client)


if __name__ == '__main__':
    Runner.sync_run(main=main())
