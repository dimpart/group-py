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
    Client Module
    ~~~~~~~~~~~~~

"""

from dimples.common.compat import LibraryLoader
from dimples.common import CommonArchivist as ClientArchivist
from dimples.group import SharedGroupManager

from dimples.client.cpu import ClientContentProcessorCreator
from dimples.client import ClientSession, SessionState
from dimples.client import ClientFacebook
from dimples.client import ClientMessenger
from dimples.client import Terminal

from .footprint import Footprint
from .emitter import Emitter

from .packer import ClientPacker
from .processor import ClientProcessor
from .processor import Service
from .service import BaseService
from .request import Request


__all__ = [

    'LibraryLoader',

    #
    #   Client
    #
    'ClientSession', 'SessionState',

    'ClientArchivist',
    'ClientFacebook',

    'ClientContentProcessorCreator',
    'ClientMessenger',
    'Terminal',

    'SharedGroupManager',
    'Footprint',
    'Emitter',

    'ClientPacker',
    'ClientProcessor',

    'Service',
    'BaseService',
    'Request',

]
