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
from typing import Optional, Union

from dimples import EntityType
from dimples import ContentType
from dimples import ContentProcessor, ContentProcessorCreator
from dimples.utils import Log

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

from libs.client.cpu import ForwardContentProcessor
from libs.client import ClientProcessor, ClientContentProcessorCreator

from bots.shared import start_bot


class AssistantContentProcessorCreator(ClientContentProcessorCreator):

    # Override
    def create_content_processor(self, msg_type: Union[int, ContentType]) -> Optional[ContentProcessor]:
        # text
        if msg_type == ContentType.FORWARD:
            return ForwardContentProcessor(facebook=self.facebook, messenger=self.messenger)
        # others
        return super().create_content_processor(msg_type=msg_type)


class AssistantProcessor(ClientProcessor):

    # Override
    def _create_creator(self) -> ContentProcessorCreator:
        return AssistantContentProcessorCreator(facebook=self.facebook, messenger=self.messenger)


#
# show logs
#
Log.LEVEL = Log.DEVELOP


DEFAULT_CONFIG = '/etc/dim_bots/config.ini'


if __name__ == '__main__':
    terminal = start_bot(default_config=DEFAULT_CONFIG,
                         app_name='DIM Group Assistant',
                         ans_name='assistant',
                         processor_class=AssistantProcessor)
    messenger = terminal.messenger
    facebook = messenger.facebook
    current_user = facebook.current_user
    bot_id = current_user.identifier
    assert bot_id.type == EntityType.BOT, 'bot ID error: %s' % current_user
