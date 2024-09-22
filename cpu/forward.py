# -*- coding: utf-8 -*-
# ==============================================================================
# MIT License
#
# Copyright (c) 2023 Albert Moky
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

from typing import List

from dimples import ReliableMessage
from dimples import Content, ForwardContent
from dimples import BaseContentProcessor
from dimples import CommonFacebook, CommonMessenger

from .handler import GroupMessageHandler


class ForwardContentProcessor(BaseContentProcessor):
    """
        Forward Content Processor
        ~~~~~~~~~~~~~~~~~~~~~~~~~

    """

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
    async def process_content(self, content: Content, r_msg: ReliableMessage) -> List[Content]:
        assert isinstance(content, ForwardContent), 'forward content error: %s' % content
        secrets = content.secrets
        messenger = self.messenger
        handler = GroupMessageHandler()
        responses = []
        for item in secrets:
            receiver = item.receiver
            group = item.group
            if receiver.is_group:
                # group message
                assert not receiver.is_broadcast, 'message error: %s => %s' % (item.sender, receiver)
                handler.append_message(msg=item)
                results = []
            elif receiver.is_broadcast and group is not None:
                # group command
                assert not group.is_broadcast, 'message error: %s => %s (%s)' % (item.sender, receiver, group)
                handler.append_message(msg=item)
                results = []
            else:
                results = await messenger.process_reliable_message(msg=item)
            # NOTICE: append one result for each forwarded message.
            if len(results) == 1:
                res = ForwardContent.create(message=results[0])
            else:
                res = ForwardContent.create(messages=results)
            responses.append(res)
        return responses
