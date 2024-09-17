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

import threading
from abc import ABC, abstractmethod
from typing import Optional, List, Dict

from dimples import ID
from dimples import Content, Envelope
from dimples import TextContent, FileContent, CustomizedContent

from ..utils import Runner

from .processor import Service
from .request import Request
from .emitter import Emitter


class BaseService(Runner, Service, ABC):

    def __init__(self):
        super().__init__(interval=Runner.INTERVAL_SLOW)
        self.__lock = threading.Lock()
        self.__requests = []

    def _add_request(self, content: Content, envelope: Envelope):
        with self.__lock:
            req = Request(envelope=envelope, content=content)
            self.__requests.append(req)

    def _next_request(self) -> Optional[Request]:
        with self.__lock:
            if len(self.__requests) > 0:
                return self.__requests.pop(0)

    # Override
    async def handle_request(self, content: Content, envelope: Envelope) -> Optional[List[Content]]:
        if isinstance(content, TextContent):
            self._add_request(content=content, envelope=envelope)
            return []
        elif isinstance(content, FileContent):
            self._add_request(content=content, envelope=envelope)
            return []
        elif isinstance(content, CustomizedContent):
            mod = content.module
            if mod == 'users':
                self._add_request(content=content, envelope=envelope)
                return []

    # Override
    async def process(self) -> bool:
        request = self._next_request()
        if request is None:
            # nothing to do now, return False to have a rest. ^_^
            return False
        content = request.content
        if isinstance(content, TextContent):
            await self._process_text_content(content=content, request=request)
        elif isinstance(content, FileContent):
            await self._process_file_content(content=content, request=request)
        elif isinstance(content, CustomizedContent):
            await self._process_customized_content(content=content, request=request)
        # task done,
        # return True to process next immediately
        return True

    @abstractmethod
    async def _process_text_content(self, content: TextContent, request: Request):
        raise NotImplemented

    @abstractmethod
    async def _process_file_content(self, content: FileContent, request: Request):
        raise NotImplemented

    @abstractmethod
    async def _process_customized_content(self, content: CustomizedContent, request: Request):
        raise NotImplemented

    #
    #   Responses
    #

    async def respond_markdown(self, text: str, request: Request, extra: Dict = None,
                               sn: int = 0, muted: str = None) -> TextContent:
        if extra is None:
            extra = {}
        else:
            extra = extra.copy()
        # extra info
        extra['format'] = 'markdown'
        if sn > 0:
            extra['sn'] = sn
        if muted is not None:
            extra['muted'] = muted
        return await self.respond_text(text=text, request=request, extra=extra)

    async def respond_text(self, text: str, request: Request, extra: Dict = None) -> TextContent:
        content = TextContent.create(text=text)
        if extra is not None:
            for key in extra:
                content[key] = extra[key]
        calibrate_time(content=content, request=request)
        await self._send_content(content=content, receiver=request.identifier)
        return content

    # noinspection PyMethodMayBeStatic
    async def _send_content(self, content: Content, receiver: ID):
        emitter = Emitter()
        return await emitter.send_content(content=content, receiver=receiver)


def calibrate_time(content: Content, request: Request, period: float = 1.0):
    res_time = content.time
    req_time = request.time
    if req_time is None:
        assert False, 'request error: %s' % req_time
    elif res_time is None or res_time <= req_time:
        content['time'] = req_time + period
