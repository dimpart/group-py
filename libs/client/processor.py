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

from abc import ABC, abstractmethod
from typing import Optional, List

from dimples import ReliableMessage
from dimples import Content, Envelope
from dimples import CommonFacebook, CommonMessenger

from dimples.client import ClientMessageProcessor

from .footprint import Footprint


class Service(ABC):
    """ Service Handler """

    @abstractmethod
    async def handle_request(self, content: Content, envelope: Envelope) -> Optional[List[Content]]:
        """
        Process content

        :param content:  request body
        :param envelope: request head
        :return: None to pass this content to system
        """
        raise NotImplemented


class ClientProcessor(ClientMessageProcessor, ABC):

    def __init__(self, facebook: CommonFacebook, messenger: CommonMessenger):
        super().__init__(facebook=facebook, messenger=messenger)
        self.__service = self._create_service()

    @property
    def facebook(self) -> CommonFacebook:
        barrack = super().facebook
        assert isinstance(barrack, CommonFacebook), 'facebook error: %s' % barrack
        return barrack

    @abstractmethod
    def _create_service(self) -> Service:
        """ Create Service Handler """
        raise NotImplemented

    # Override
    async def process_content(self, content: Content, r_msg: ReliableMessage) -> List[Content]:
        fp = Footprint()
        await fp.touch(identifier=r_msg.sender, when=content.time)
        service = self.__service
        responses = await service.handle_request(content=content, envelope=r_msg.envelope)
        if responses is None:
            responses = await super().process_content(content=content, r_msg=r_msg)
        return responses
