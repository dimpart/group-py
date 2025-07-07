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
from typing import Optional

from dimples import EntityType, ID
from dimples import TextContent, FileContent

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from libs.utils import Runner
from libs.utils import Log
from libs.utils import Config

from libs.client import ClientProcessor
from libs.client import SharedGroupManager
from libs.client import Footprint
from libs.client import Service, Request, BaseService

from bots.shared import GlobalVariable
from bots.shared import create_config, start_bot


class Vars:
    """ Global Vars """
    current_group: Optional[ID] = None


class GroupUsher(BaseService):

    # list foot
    LIST_DESC = ''

    @property
    def config(self) -> Config:
        shared = GlobalVariable()
        return shared.config

    @property
    def facebook(self):
        shared = GlobalVariable()
        return shared.facebook

    async def __group_info(self, group: ID) -> str:
        """ build group info """
        facebook = self.facebook
        doc = await facebook.get_document(identifier=group)
        if doc is None:
            self.error(msg='group not ready: %s' % group)
            name = group.name
        else:
            name = doc.name
        # name = md_esc(text=name)
        return '- Name: ***"%s"***\n- ID  : %s\n' % (name, group)

    async def __query_current_group(self, request: Request):
        current = Vars.current_group
        if isinstance(current, ID):
            text = 'Current group is:\n%s' % await self.__group_info(group=current)
            await self.respond_markdown(text=text, request=request)
            return True
        else:
            text = 'current group not set yet'
            await self.respond_text(text=text, request=request)
            return False

    async def __set_current_group(self, request: Request):
        sender = request.envelope.sender
        group = request.content.group
        if group is None:
            text = 'Call me in the group'
            await self.respond_text(text=text, request=request)
        else:
            old = Vars.current_group
            self.warning(msg='change current group by %s: %s -> %s' % (sender, old, group))
            Vars.current_group = group
            text = 'Current group set to:\n%s' % await self.__group_info(group=group)
            if old is not None:
                assert isinstance(old, ID), 'old group ID error: %s' % old
                text += '\n'
                text += 'replacing the old one:\n%s' % await self.__group_info(group=old)
            await self.respond_markdown(text=text, request=request)

    async def __show_active_users(self, request: Request):
        sender = request.sender
        facebook = self.facebook
        fp = Footprint()
        users = await fp.active_users()
        active_users = []
        # build text
        text = '## Active Users\n'
        text += '| Name | Last Time |\n'
        text += '|------|-----------|\n'
        for item in users:
            uid = item.identifier
            if uid.type != EntityType.USER:
                self.info(msg='ignore user: %s' % uid)
                continue
            elif uid == sender:
                self.info(msg='skip the sender: %s' % uid)
                continue
            # get nickname
            visa = await facebook.get_visa(user=uid)
            name = None if visa is None else visa.name
            if name is None or len(name) == 0:
                name = uid.name
                if name is None or len(name) == 0:
                    name = str(uid)
            when = str(item.time)
            if len(when) == 19:
                when = when[5:-3]
            text += '| %s | _%s_ |\n' % (name, when)
            active_users.append(str(uid))
        text += '\n'
        text += 'Totally %d users.' % len(active_users)
        # search tag
        content = request.content
        tag = content.get('tag')
        title = content.get('title')
        keywords = content.get('keywords')
        hidden = content.get('hidden')
        self.info(msg='respond %d/%d users, tag %s, %s' % (len(active_users), len(users), tag, request.identifier))
        return await self.respond_text(text=text, request=request, extra={
            'format': 'markdown',
            'muted': hidden,
            'hidden': hidden,

            'app': 'chat.dim.search',
            'mod': 'users',
            'act': 'respond',
            'expires': 600,

            'tag': tag,
            'title': title,
            'keywords': keywords,

            'users': active_users,
            'description': self.LIST_DESC,
        })

    ADMIN_COMMANDS = [
        'help',
        'current group',
        'set current group',
    ]

    HELP_PROMPT = '## Admin Commands\n' \
                  '* current group\n' \
                  '* set current group\n'

    async def _process_admin_command(self, command: str, request: Request):
        sender = request.envelope.sender
        # check permissions before executing command
        supervisors = await self.config.get_supervisors(facebook=self.facebook)
        if sender not in supervisors:
            self.warning(msg='permission denied: "%s", sender: %s' % (command, sender))
            text = 'Forbidden\n'
            text += '\n----\n'
            text += 'Permission Denied'
            return await self.respond_markdown(text=text, request=request)
        elif command == 'help':
            #
            #  usages
            #
            return await self.respond_markdown(text=self.HELP_PROMPT, request=request)
        #
        #  group commands
        #
        if command == 'set current group':
            #
            #  change current group
            #
            return await self.__set_current_group(request=request)
        elif command == 'current group':
            #
            #  show current group
            #
            return await self.__query_current_group(request=request)

    # Override
    async def _process_text_content(self, content: TextContent, request: Request):
        # get keywords as command
        keywords = content.get_str(key='keywords', default='')
        if len(keywords) == 0:
            keywords = content.get_str(key='title', default='')
            if len(keywords) == 0:
                keywords = await request.get_text(facebook=self.facebook)
                if keywords is None:
                    # self.error(msg='text content error: %s' % content)
                    return
        self.info(msg='process keywords: "%s"' % keywords)
        command = keywords.strip().lower()
        if command in self.ADMIN_COMMANDS:
            # group commands
            await self._process_admin_command(command=command, request=request)
        elif command == 'active users':
            #
            #  show recently active users
            #
            return await self.__show_active_users(request=request)
        else:
            text = 'Unexpected command: "%s"' % keywords
            await self.respond_text(text=text, request=request)

    # Override
    async def _process_file_content(self, content: FileContent, request: Request):
        if content.group is None:
            text = 'Cannot process file contents now.'
            await self.respond_text(text=text, request=request)

    # Override
    async def _process_new_user(self, identifier: ID):
        # check current group
        group = Vars.current_group
        if group is None:
            self.warning(msg='group ID not set')
            return False
        # check members
        members = await self.facebook.get_members(identifier=group)
        if members is None or len(members) == 0:
            self.error(msg='group not ready: %s' % group)
            return False
        assert identifier.type == EntityType.USER, 'user error: %s' % identifier
        if identifier in members:
            self.info(msg='member already exists: %s -> %s' % (identifier, group))
            return False
        self.info(msg='invite %s into group: %s' % (identifier, group))
        man = SharedGroupManager()
        return await man.invite_group_members(members=[identifier], group=group)


class BotMessageProcessor(ClientProcessor):

    # Override
    def _create_service(self) -> Service:
        service = GroupUsher()
        service.start()
        return service


#
# show logs
#
Log.LEVEL = Log.DEVELOP


DEFAULT_CONFIG = '/etc/dim/group.ini'


async def async_main():
    # create global variable
    shared = GlobalVariable()
    config = await create_config(app_name='GroupBot: Usher', default_config=DEFAULT_CONFIG)
    await shared.prepare(config=config)
    #
    #  Create & start the bot
    #
    client = await start_bot(ans_name='usher', processor_class=BotMessageProcessor)
    Log.warning(msg='bot stopped: %s' % client)


def main():
    Runner.sync_run(main=async_main())


if __name__ == '__main__':
    main()
