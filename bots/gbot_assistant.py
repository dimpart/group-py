#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# MIT License
#
# Copyright (c) 2019 Albert Moky
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
    Group bot: 'assistant'
    ~~~~~~~~~~~~~~~~~~~~~~

    Bot for collecting and responding group member list
"""

import sys
import os
from typing import Optional

from dimples import ID
from dimples import FileContent, TextContent
from dimples import ContentType
from dimples import ContentProcessor, ContentProcessorCreator
from dimples import Facebook, Messenger

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from libs.utils import Log, Runner
from libs.client import ClientContentProcessorCreator
from libs.client import ClientProcessor
from libs.client import Service, Request, BaseService

from cpu import CustomizedProcessor
from cpu import ForwardContentProcessor
from cpu import GroupMessageDistributor

from bots.shared import GlobalVariable
from bots.shared import create_config, start_bot


class GroupService(BaseService):

    # Override
    async def _process_text_content(self, content: TextContent, request: Request):
        text = content.text
        self.info(msg='received text message from %s: "%s"' % (request.sender, text))

    # Override
    async def _process_file_content(self, content: FileContent, request: Request):
        self.info(msg='received file from %s: %s' % (request.sender, content))

    # Override
    async def _process_new_user(self, identifier: ID):
        distributor = GroupMessageDistributor()
        distributor.wakeup_user(identifier=identifier)


class AssistantContentProcessorCreator(ClientContentProcessorCreator):

    # Override
    def create_content_processor(self, msg_type: str) -> Optional[ContentProcessor]:
        # forward
        if msg_type == ContentType.FORWARD:
            return ForwardContentProcessor(facebook=self.facebook, messenger=self.messenger)
        # customized
        if msg_type == ContentType.CUSTOMIZED:
            return CustomizedProcessor(facebook=self.facebook, messenger=self.messenger)
        # others
        return super().create_content_processor(msg_type=msg_type)


class AssistantProcessor(ClientProcessor):

    # Override
    def _create_service(self) -> Service:
        service = GroupService()
        service.start()
        return service

    # Override
    def _create_creator(self, facebook: Facebook, messenger: Messenger) -> ContentProcessorCreator:
        return AssistantContentProcessorCreator(facebook=self.facebook, messenger=self.messenger)


#
# show logs
#
Log.LEVEL = Log.DEVELOP


DEFAULT_CONFIG = '/etc/dim/group.ini'


async def async_main():
    # create global variable
    shared = GlobalVariable()
    config = await create_config(app_name='DIM Group Assistant', default_config=DEFAULT_CONFIG)
    await shared.prepare(config=config)
    #
    #  Create & start the bot
    #
    client = await start_bot(ans_name='assistant', processor_class=AssistantProcessor)
    Log.warning(msg='bot stopped: %s' % client)


def main():
    Runner.sync_run(main=async_main())


if __name__ == '__main__':
    main()
