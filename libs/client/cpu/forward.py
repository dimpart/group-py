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
from dimples import Content, ForwardContent, ArrayContent
from dimples import BaseContentProcessor
from dimples import CommonFacebook, CommonMessenger


def forward_messages(messages: List[ReliableMessage]) -> List[Content]:
    """ Convert reliable messages to forward contents """
    return [] if len(messages) == 0 else [ForwardContent.create(messages=messages)]


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
        array = []
        for item in secrets:
            receiver = item.receiver
            group = item.group
            if receiver.is_group:
                # group message
                assert not receiver.is_broadcast, 'message error: %s => %s' % (item.sender, receiver)
                results = self.__split_group_message(group=receiver, content=content, msg=item)
            elif receiver.is_broadcast and group is not None:
                # group command
                assert not group.is_broadcast, 'message error: %s => %s (%s)' % (item.sender, receiver, group)
                results = self.__process_group_command(group=group, content=content, msg=item)
            else:
                responses = messenger.process_reliable_message(msg=item)
                results = forward_messages(messages=responses)
            # NOTICE: append one result for each forwarded message here.
            #         if result is more than one content, append an array content;
            #         if result is empty, append an empty array content too.
            if len(results) == 1:
                array.append(results[0])
            else:
                array.append(ArrayContent.create(contents=results))
        return array

    def __split_group_message(self, group: ID, content: Content, msg: ReliableMessage) -> List[Content]:
        facebook = self.facebook
        # 1. check members
        members = facebook.members(identifier=group)
        sender = msg.sender
        if sender not in members:
            return self._respond_receipt(text='Permission denied.', content=content, envelope=msg.envelope, extra={
                'template': 'You are not a member of group: ${ID}',
                'replacements': {
                    'ID': str(group),
                }
            })
        recipients = members.copy()
        # 2. deliver group message for each members
        recipients.remove(sender)
        return self.__distribute_group_message(recipients=recipients, group=group, content=content, msg=msg)

    def __process_group_command(self, group: ID, content: Content, msg: ReliableMessage) -> List[Content]:
        facebook = self.facebook
        messenger = self.messenger
        # 1. get members before
        members = facebook.members(identifier=group)
        sender = msg.sender
        if sender not in members:
            text = 'Permission denied.'
            return self._respond_receipt(text=text, content=content, envelope=msg.envelope, extra={
                'template': 'You are not a member of group: ${ID}',
                'replacements': {
                    'ID': str(group),
                }
            })
        recipients = members.copy()
        # 2. process message
        responses = messenger.process_reliable_message(msg=msg)
        # 3. get members after
        members = facebook.members(identifier=group)
        for item in members:
            if item not in recipients:
                recipients.append(item)
        # 4. deliver group message for each members
        recipients.remove(sender)
        array = self.__distribute_group_message(recipients=recipients, group=group, content=content, msg=msg)
        # 5. merge responses
        results = forward_messages(messages=responses)
        for item in array:
            results.append(item)
        return results

    def __distribute_group_message(self, recipients: List[ID], group: ID,
                                   content: Content, msg: ReliableMessage) -> List[Content]:
        distributor = get_distributor(messenger=self.messenger)
        members, missing = distributor.deliver(msg=msg, group=group, recipients=recipients)
        # OK
        text = 'Group messages are distributing.'
        return self._respond_receipt(text=text, content=content, envelope=msg.envelope, extra={
            'template': 'Group messages are distributing to members: ${members}',
            'replacements': {
                'members': ID.revert(array=members),
            },
            'missing_keys': ID.revert(array=missing)
        })


def get_distributor(messenger: CommonMessenger):
    from ..receptionist import Receptionist
    receptionist = Receptionist()
    receptionist.messenger = messenger
    return receptionist.distributor
