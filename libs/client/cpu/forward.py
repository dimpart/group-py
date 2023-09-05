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

from dimples import ID, ReliableMessage
from dimples import Content, ForwardContent
from dimples import BaseContentProcessor
from dimples import CommonFacebook, CommonMessenger


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
    def process_content(self, content: Content, r_msg: ReliableMessage) -> List[Content]:
        assert isinstance(content, ForwardContent), 'forward content error: %s' % content
        secrets = content.secrets
        messenger = self.messenger
        responses = []
        for item in secrets:
            receiver = item.receiver
            if receiver.is_group:
                # group message
                res = self.__split_group_message(group=receiver, msg=item)
            elif receiver.is_broadcast and item.group is not None:
                # group command
                res = self.__process_group_command(group=item.group, msg=item)
            else:
                results = messenger.process_reliable_message(msg=item)
                if len(results) == 1:
                    res = ForwardContent.create(message=results[0])
                else:
                    res = ForwardContent.create(messages=results)
            responses.append(res)
        return responses

    def __split_group_message(self, group: ID, msg: ReliableMessage) -> Content:
        facebook = self.facebook
        # 1. check members
        members = facebook.members(identifier=group)
        sender = msg.sender
        if sender not in members:
            return self._respond_receipt(text='Permission denied.', msg=msg, group=group, extra={
                'template': 'You are not a member of group: ${ID}',
                'replacements': {
                    'ID': str(group),
                }
            })[0]
        recipients = members.copy()
        # 2. deliver group message for each members
        recipients.remove(sender)
        return self.__distribute_group_message(msg=msg, group=group, recipients=recipients)

    def __process_group_command(self, group: ID, msg: ReliableMessage) -> Content:
        facebook = self.facebook
        messenger = self.messenger
        # 1. get members before
        members = facebook.members(identifier=group)
        sender = msg.sender
        if sender not in members:
            return self._respond_receipt(text='Permission denied.', msg=msg, group=group, extra={
                'template': 'You are not a member of group: ${ID}',
                'replacements': {
                    'ID': str(group),
                }
            })[0]
        recipients = members.copy()
        # 2. process message
        messenger.process_reliable_message(msg=msg)
        # 3. get members after
        members = facebook.members(identifier=group)
        for item in members:
            if item not in recipients:
                recipients.append(item)
        # 4. deliver group message for each members
        recipients.remove(sender)
        return self.__distribute_group_message(msg=msg, group=group, recipients=recipients)

    def __distribute_group_message(self, msg: ReliableMessage, group: ID, recipients: List[ID]) -> Content:
        distributor = get_distributor()
        members = []
        for item in recipients:
            if distributor.deliver(receiver=item, msg=msg):
                members.append(item)
        # OK
        return self._respond_receipt(text='Group messages are distributing.', msg=msg, group=group, extra={
            'template': 'Group messages are distributing to members: ${members}',
            'replacements': {
                'members': ID.revert(array=members),
            }
        })[0]


def get_distributor():
    from ..distributor import Distributor
    return Distributor()
