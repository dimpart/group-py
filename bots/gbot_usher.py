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
from typing import List

from dimples import EntityType, ID
from dimples import TextContent, FileContent

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from libs.utils import Runner
from libs.utils import Log

from libs.client import ClientProcessor
from libs.client import SharedGroupManager
from libs.client import Footprint
from libs.client import Service, Request, BaseService

from bots.shared import GlobalVariable
from bots.shared import create_config, start_bot


g_vars = {
    'group': None,
    'supervisors': [],
}


class GroupUsher(BaseService):

    # list foot
    LIST_DESC = ''

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
        current = g_vars.get('group')
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
            text = 'Permission denied.'
            await self.respond_text(text=text, request=request)
            return False

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

    # Override
    async def _process_new_user(self, identifier: ID):
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
        assert identifier.type == EntityType.USER, 'user error: %s' % identifier
        if identifier in members:
            self.info(msg='member already exists: %s -> %s' % (identifier, group))
            return False
        self.info(msg='invite %s into group: %s' % (identifier, group))
        gm = SharedGroupManager()
        return await gm.invite_members(members=[identifier], group=group)

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
        command = keywords.strip().lower()
        # group commands
        if command == 'set current group':
            return await self.__set_current_group(request=request)
        elif command == 'current group':
            return await self.__query_current_group(request=request)
        elif command == 'active users':
            return await self.__show_active_users(request=request)
        else:
            text = 'Unexpected command: "%s"' % keywords
            await self.respond_text(text=text, request=request)

    # Override
    async def _process_file_content(self, content: FileContent, request: Request):
        if content.group is None:
            text = 'Cannot process file contents now.'
            await self.respond_text(text=text, request=request)


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


DEFAULT_CONFIG = '/etc/dim_bots/config.ini'


async def async_main():
    # create global variable
    shared = GlobalVariable()
    config = await create_config(app_name='GroupBot: Usher', default_config=DEFAULT_CONFIG)
    await shared.prepare(config=config)
    #
    #  Set supervisors
    #
    supervisors = shared.config.get_list(section='group', option='supervisors')
    if isinstance(supervisors, List):
        g_vars['supervisors'] = ID.convert(array=supervisors)
    #
    #  Create & start the bot
    #
    client = await start_bot(ans_name='usher', processor_class=BotMessageProcessor)
    Log.warning(msg='bot stopped: %s' % client)


def main():
    Runner.sync_run(main=async_main())


if __name__ == '__main__':
    main()
