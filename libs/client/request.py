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

from typing import Optional

from dimples import DateTime
from dimples import EntityType, ID
from dimples import Content, Envelope
from dimples import CommonFacebook

from ..utils import Log, Logging


class Request(Logging):

    def __init__(self, envelope: Envelope, content: Content):
        super().__init__()
        self.__head = envelope
        self.__body = content

    @property
    def envelope(self) -> Envelope:
        return self.__head

    @property
    def content(self) -> Content:
        return self.__body

    @property
    def sender(self) -> ID:
        return self.envelope.sender

    @property
    def identifier(self) -> ID:
        group = self.content.group
        return self.sender if group is None else group

    @property
    def time(self) -> Optional[DateTime]:
        when = self.content.time
        return self.envelope.time if when is None else when

    async def get_text(self, facebook: CommonFacebook) -> Optional[str]:
        content = self.content
        text = content.get('text')
        if text is not None and len(text) > 0:
            envelope = self.envelope
            text = await filter_text(text=text, content=content, envelope=envelope, facebook=facebook)
        return text


async def filter_text(text: str, content: Content, envelope: Envelope, facebook: CommonFacebook) -> Optional[str]:
    sender = envelope.sender
    if EntityType.BOT == sender.type:
        if len(text) > 128:
            text = '%s ... %s' % (text[:100], text[-22:])
        Log.info('ignore message from another bot: %s, "%s"' % (sender, text))
        return None
    elif EntityType.STATION == sender.type:
        Log.info('ignore message from station: %s, "%s"' % (sender, text))
        return None
    # check request time
    req_time = content.time
    assert req_time is not None, 'request error: %s' % envelope
    dt = DateTime.now() - req_time
    if dt > 600:
        # Old message, ignore it
        Log.warning(msg='ignore expired message from %s: %s' % (sender, req_time))
        return None
    # check group message
    if content.group is None:
        # personal message
        return text
    # checking '@nickname '
    receiver = envelope.receiver
    bot_name = await get_nickname(identifier=receiver, facebook=facebook)
    assert bot_name is not None and len(bot_name) > 0, 'receiver error: %s' % receiver
    at = '@%s ' % bot_name
    naked = text.replace(at, '')
    at = '@%s' % bot_name
    if text.endswith(at):
        naked = naked[:-len(at)]
    if naked != text:
        return naked
    Log.info('ignore group message that not querying me(%s): %s' % (at, text))


async def get_nickname(identifier: ID, facebook: CommonFacebook) -> Optional[str]:
    visa = await facebook.get_document(identifier=identifier)
    if visa is not None:
        return visa.name
