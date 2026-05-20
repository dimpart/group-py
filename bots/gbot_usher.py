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
from typing import Optional, Dict

from dimples import DateTime, Converter
from dimples import EntityType, ID
from dimples import DocumentUtils

from dimples import TextContent, FileContent
from dimples import CustomizedContent

from dimples.utils import SysArgvParser
from dimples.utils import init_logger
from dimples.utils import Log, LogLevel, Logging
from dimples.utils import Runner, Config
from dimples.utils import Path

path = Path.abs(path=__file__)
path = Path.dir(path=path)
path = Path.dir(path=path)
Path.add(path=path)

from libs.utils import get_supervisors, md_supervisors
from libs.utils import md_user_url

from libs.client import ClientProcessor
from libs.client import SharedGroupManager
from libs.client import Footprint
from libs.client import Service, Request, BaseService

from bots.shared import GlobalVariable
from bots.shared import create_config, start_bot
from bots.shared import show_help


class Freshman(Logging):

    def __init__(self):
        super().__init__()
        self.__group: Optional[ID] = None
        self.__start_time = DateTime.now()
        self.__new_users = {}  # ID -> DateTime

    @property
    def current_group(self) -> Optional[ID]:
        return self.__group

    @current_group.setter
    def current_group(self, gid):
        self.__group = gid
        # reset after current group changed
        self.__start_time = DateTime.now()
        self.__new_users = {}

    @property
    def start_time(self) -> DateTime:
        return self.__start_time

    @property
    def new_users(self) -> Dict:
        return self.__new_users.copy()

    @property
    def facebook(self):
        shared = GlobalVariable()
        return shared.facebook

    async def _check_user(self, user: ID, group: ID) -> bool:
        facebook = self.facebook
        # check user type
        if user.type != EntityType.USER:
            self.error('user error: %s', user)
            return False
        # check user time
        visa = await facebook.get_visa(user=user)
        if visa is None:
            self.error('user not ready: %s', user)
        else:
            created_time = visa.get_property(name='created_time')
            created_time = Converter.get_datetime(value=created_time)
            if created_time is None:
                self.error('user visa error: %s', visa)
            elif self.start_time.after(other=created_time):
                # this user's created time is before the bot launched,
                # just ignore it
                self.info('ignore old user: %s', user)
                return False
        # check members
        members = await facebook.get_members(identifier=group)
        if members is None or len(members) == 0:
            self.error('group not ready: %s', group)
            return False
        if user in members:
            self.info('member already exists: %s -> %s', user, group)
            return False
        # OK
        return True

    async def process_new_user(self, identifier: ID) -> bool:
        now = DateTime.now()
        when = self.__new_users.get(identifier)
        if when is not None:
            self.__new_users[identifier] = now
        # check current group
        group = self.current_group
        if group is None:
            self.warning('group ID not set')
            return False
        if await self._check_user(user=identifier, group=group):
            self.info('invite %s into group: %s', identifier, group)
            self.__new_users[identifier] = now
            man = SharedGroupManager()
            return await man.invite_group_members(members=[identifier], group=group)


g_vars = Freshman()


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
            self.error('group not ready: %s', group)
            name = group.name
        else:
            name = DocumentUtils.get_document_name(document=doc)
        # name = md_esc(text=name)
        return f'- Name: ***"{name}"***\n- ID  : {group}\n'

    async def __query_current_group(self, request: Request):
        current = g_vars.current_group
        if isinstance(current, ID):
            grp_info = await self.__group_info(group=current)
            text = f'Current group is:\n{grp_info}'
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
            old = g_vars.current_group
            self.warning('change current group by %s: %s -> %s', sender, old, group)
            g_vars.current_group = group
            grp_info = await self.__group_info(group=group)
            text = f'Current group set to:\n{grp_info}\n'
            if old is not None:
                assert isinstance(old, ID), f'old group ID error: {old}'
                grp_info = await self.__group_info(group=old)
                text += f'replacing the old one:\n{grp_info}\n'
            await self.respond_markdown(text=text, request=request)

    async def __show_new_users(self, request: Request):
        facebook = self.facebook
        new_users = g_vars.new_users
        count = len(new_users)
        # build text
        text = '## New Users\n'
        text += '| Name | Last Time |\n'
        text += '|------|-----------|\n'
        for uid in new_users:
            # get user info
            visa = await facebook.get_visa(user=uid)
            if visa is None:
                title = f'**{uid}**'
            else:
                title = md_user_url(visa=visa)
            when = str(new_users.get(uid))
            if len(when) == 19:
                when = when[5:-3]
            text += f'| {title} | _{when}_ |\n'
        text += '\n'
        text += f'Totally {count} new users from {g_vars.start_time}.'
        self.info('respond %d new users, %s', count, request.identifier)
        return await self.respond_text(text=text, request=request, extra={
            'format': 'markdown',
        })

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
                self.info('ignore user: %s', uid)
                continue
            elif uid == sender:
                self.info('skip the sender: %s', uid)
                continue
            # get user info
            visa = await facebook.get_visa(user=uid)
            if visa is None:
                title = f'**{uid}**'
            else:
                title = md_user_url(visa=visa)
            when = str(item.time)
            if len(when) == 19:
                when = when[5:-3]
            text += f'| {title} | _{when}_ |\n'
            active_users.append(str(uid))
        text += '\n'
        text += f'Totally {len(active_users)} users.'
        # search tag
        content = request.content
        tag = content.get('tag')
        title = content.get('title')
        keywords = content.get('keywords')
        hidden = content.get('hidden')
        self.info('respond %d/%d users, tag %s, %s', len(active_users), len(users), tag, request.identifier)
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
        'current group',
        'set current group',
    ]

    HELP_PROMPT = '## Admin Commands\n' \
                  '* current group\n' \
                  '* set current group\n'

    async def _help_info(self) -> str:
        # get supervisors from config
        text = await md_supervisors(config=self.config, facebook=self.facebook, section='usher')
        return f'{self.HELP_PROMPT}\n\n## Supervisors\n{text}'

    async def _process_admin_command(self, command: str, request: Request):
        sender = request.envelope.sender
        # check permissions before executing command
        self.info('process admin command: "%s"', command)
        supervisors = await get_supervisors(config=self.config, facebook=self.facebook, section='usher')
        # check permissions before executing command
        if sender not in supervisors:
            self.warning('permission denied: "%s", sender: %s', command, sender)
            text = 'Forbidden\n'
            text += '\n----\n'
            text += 'Permission Denied'
            return await self.respond_markdown(text=text, request=request)
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
        keywords = content.get_str(key='keywords')
        if keywords is None or len(keywords) == 0:
            keywords = content.get_str(key='title')
            if keywords is None or len(keywords) == 0:
                keywords = await request.get_text(facebook=self.facebook)
                if keywords is None:
                    self.error('text content error: %s', content)
                    return
        self.info('process keywords: "%s"', keywords)
        command = keywords.strip()
        if command == 'help':
            #
            #  usages
            #
            text = await self._help_info()
            await self.respond_markdown(text=text, request=request)
        elif command in self.ADMIN_COMMANDS:
            #
            #  group commands
            #
            await self._process_admin_command(command=command, request=request)
        elif command == 'new users':
            #
            #  show recently registered users
            #
            await self.__show_new_users(request=request)
        elif command == 'active users':
            #
            #  show recently active users
            #
            await self.__show_active_users(request=request)
        else:
            #
            #  error
            #
            text = f'Unexpected command: "{keywords}"'
            await self.respond_text(text=text, request=request)

    # Override
    async def _process_file_content(self, content: FileContent, request: Request):
        if content.group is None:
            text = 'Cannot process file contents now.'
            await self.respond_text(text=text, request=request)

    # Override
    async def _process_customized_content(self, content: CustomizedContent, request: Request):
        # app = content.application
        app = content.get_str(key='app')
        mod = content.module
        act = content.action
        if app == 'chat.dim.session':
            if mod == 'users' and act == 'request':
                #
                #  show recently active users
                #
                await self.__show_active_users(request=request)
            else:
                # error
                sender = request.envelope.sender
                self.error('content error: app="%s" mod="%s" act="%s", sender: %s', app, mod, act, sender)
        else:
            # app == 'chat.dim.monitor' and mod == 'users' and act == 'post'
            await super()._process_customized_content(content=content, request=request)

    # Override
    async def _process_new_user(self, identifier: ID):
        try:
            await g_vars.process_new_user(identifier=identifier)
        except Exception as error:
            self.error('failed to process new user: %s, error: %s', identifier, error)


class BotMessageProcessor(ClientProcessor):

    # Override
    def _create_service(self) -> Service:
        service = GroupUsher()
        service.start()
        return service


#
#  show logs
#
LOG_LEVEL = LogLevel.DEVELOP

BOT_NAME = 'usher'

APP_NAME = 'GroupBot: Usher'

DEFAULT_CONFIG = '/etc/dim/group.ini'


async def async_main():
    #
    #  parse cmd parameters
    #
    sys_argv = SysArgvParser.parse(shortopts='hf:ld:',
                                   longopts=['help', 'config=', 'log-location', 'log-dir='])
    if sys_argv is None:
        show_help(app_name=APP_NAME, cmd=sys.argv[0], default_config=DEFAULT_CONFIG)
        sys.exit(1)
    #
    #  init logger
    #
    show_location = sys_argv.has_opt(opt='log-location')
    init_logger(name=BOT_NAME, level=LOG_LEVEL, show_location=show_location)
    #
    #  create config
    #
    config = await create_config(sys_argv=sys_argv, default_config=DEFAULT_CONFIG)
    if config is None:
        show_help(app_name=APP_NAME, cmd=sys.argv[0], default_config=DEFAULT_CONFIG)
        sys.exit(1)
    #
    #  Create & start the bot
    #
    client = await start_bot(ans_name=BOT_NAME, processor_class=BotMessageProcessor)
    Log.warning('bot stopped: %s', client)


def main():
    Runner.sync_run(main=async_main())


if __name__ == '__main__':
    main()
