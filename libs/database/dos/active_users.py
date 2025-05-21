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

from typing import List

from dimples.database.dos import Storage

from ...common.dbi import ActiveUser, ActiveUserDBI


class ActiveUserStorage(Storage, ActiveUserDBI):
    """
        Active Users
        ~~~~~~~~~~~~

        file path: '.dim/protected/active_users.js'
    """
    active_users_path = '{PROTECTED}/active_users.js'

    def show_info(self):
        path = self.protected_path(self.active_users_path)
        print('!!!   active users path: %s' % path)

    def __active_users_path(self) -> str:
        return self.protected_path(self.active_users_path)

    # Override
    async def load_active_users(self) -> List[ActiveUser]:
        path = self.__active_users_path()
        self.info('Loading active users from: %s' % path)
        array = await self.read_json(path=path)
        if array is None:
            return []
        else:
            return ActiveUser.convert(array=array)

    # Override
    async def save_active_users(self, users: List[ActiveUser]) -> bool:
        array = ActiveUser.revert(array=users)
        path = self.__active_users_path()
        self.info('Saving %d active users into: %s' % (len(users), path))
        return await self.write_json(container=array, path=path)
