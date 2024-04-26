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

from abc import abstractmethod
from typing import Optional, List, Tuple

from dimples import DateTime
from dimples import ID, EntityType
from dimples import Envelope, Content
from dimples import TextContent
from dimples import CommonFacebook

from ..utils import Logging

from .emitter import Emitter


Request = Tuple[Envelope, Content]


class ChatBoxMixIn(Logging):

    @property
    @abstractmethod
    def facebook(self) -> CommonFacebook:
        raise NotImplemented

    def _fetch_text(self, content: TextContent, envelope: Envelope) -> Optional[str]:
        sender = envelope.sender
        text = content.text
        if EntityType.BOT == sender.type:
            self.info('ignore message from another bot: %s, "%s"' % (sender, text))
            return None
        elif EntityType.STATION == sender.type:
            self.info('ignore message from station: %s, "%s"' % (sender, text))
            return None
        # check request time
        req_time = content.time
        assert req_time is not None, 'request error: %s' % self
        dt = DateTime.now() - req_time
        if dt > 600:
            # Old message, ignore it
            self.warning(msg='ignore expired message from %s: %s' % (sender, req_time))
            return None
        # check group message
        if content.group is None:
            # personal message
            return text
        # checking '@nickname '
        receiver = envelope.receiver
        bot_name = get_nickname(identifier=receiver, facebook=self.facebook)
        assert bot_name is not None and len(bot_name) > 0, 'receiver error: %s' % receiver
        at = '@%s ' % bot_name
        naked = text.replace(at, '')
        at = '@%s' % bot_name
        if text.endswith(at):
            naked = naked[:-len(at)]
        if naked != text:
            return naked
        self.info('ignore group message that not querying me(%s): %s' % (at, text))

    #
    #   Respond
    #

    def respond_text(self, text: str, request: Request) -> int:
        content = TextContent.create(text=text)
        calibrate_time(content=content, request=request)
        return self.respond(responses=[content], request=request)

    def respond(self, responses: List[Content], request: Request) -> int:
        # all content time in responses must be calibrated with the request time
        receiver = request[1].group
        if receiver is None:
            receiver = request[0].sender
        for res in responses:
            self._send_content(content=res, receiver=receiver)
        return len(responses)

    # noinspection PyMethodMayBeStatic
    def _send_content(self, content: Content, receiver: ID):
        """ Send message to DIM station """
        emitter = Emitter()
        emitter.send_content(content=content, receiver=receiver)


def calibrate_time(content: Content, request: Request, period: float = 1.0):
    res_time = content.time
    req_time = request[1].time
    if req_time is None:
        assert False, 'request error: %s' % req_time
    elif res_time is None or res_time <= req_time:
        content['time'] = req_time + period


def get_nickname(identifier: ID, facebook: CommonFacebook) -> Optional[str]:
    visa = facebook.document(identifier=identifier)
    if visa is not None:
        return visa.name
