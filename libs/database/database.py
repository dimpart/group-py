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
    Database module
    ~~~~~~~~~~~~~~~

"""

from typing import Optional, Dict, List, Tuple

from dimples import SymmetricKey, PrivateKey, SignKey, DecryptKey
from dimples import ID, Meta, Document
from dimples import ReliableMessage
from dimples import LoginCommand, GroupCommand, ResetCommand
from dimples import AccountDBI, MessageDBI, SessionDBI
from dimples.common.dbi import ProviderInfo, StationInfo
from dimples.database.t_private import PrivateKeyTable
from dimples.database.t_cipherkey import CipherKeyTable

# from .t_ans import AddressNameTable
from .t_meta import MetaTable
from .t_document import DocumentTable
from .t_group import GroupTable
from .t_grp_history import GroupHistoryTable
from .t_group_keys import GroupKeysTable
from .t_group_inbox import GroupInboxMessageTable


class Database(AccountDBI, MessageDBI, SessionDBI):

    def __init__(self, root: str = None, public: str = None, private: str = None):
        super().__init__()
        self.__users = []
        self.__contacts = {}
        # Entity
        self.__private_table = PrivateKeyTable(root=root, public=public, private=private)
        self.__meta_table = MetaTable(root=root, public=public, private=private)
        self.__document_table = DocumentTable(root=root, public=public, private=private)
        self.__group_table = GroupTable(root=root, public=public, private=private)
        self.__history_table = GroupHistoryTable(root=root, public=public, private=private)
        # Message
        self.__grp_keys_table = GroupKeysTable(root=root, public=public, private=private)
        self.__cipherkey_table = CipherKeyTable(root=root, public=public, private=private)
        self.__inbox_table = GroupInboxMessageTable(root=root, public=public, private=private)
        # # ANS
        # self.__ans_table = AddressNameTable(root=root, public=public, private=private)

    def show_info(self):
        # Entity
        self.__private_table.show_info()
        self.__meta_table.show_info()
        self.__document_table.show_info()
        self.__group_table.show_info()
        self.__history_table.show_info()
        self.__grp_keys_table.show_info()
        self.__cipherkey_table.show_info()
        # # ANS
        # self.__ans_table.show_info()

    """
        Private Key file for Users
        ~~~~~~~~~~~~~~~~~~~~~~~~~~

        file path: '.dim/private/{ADDRESS}/secret.js'
        file path: '.dim/private/{ADDRESS}/secret_keys.js'
    """

    # Override
    def save_private_key(self, key: PrivateKey, user: ID, key_type: str = 'M') -> bool:
        return self.__private_table.save_private_key(key=key, user=user, key_type=key_type)

    # Override
    def private_keys_for_decryption(self, user: ID) -> List[DecryptKey]:
        return self.__private_table.private_keys_for_decryption(user=user)

    # Override
    def private_key_for_signature(self, user: ID) -> Optional[SignKey]:
        return self.__private_table.private_key_for_signature(user=user)

    # Override
    def private_key_for_visa_signature(self, user: ID) -> Optional[SignKey]:
        return self.__private_table.private_key_for_visa_signature(user=user)

    """
        Meta file for entities
        ~~~~~~~~~~~~~~~~~~~~~~

        file path: '.dim/public/{ADDRESS}/meta.js'
        redis key: 'mkm.meta.{ID}'
    """

    # Override
    def save_meta(self, meta: Meta, identifier: ID) -> bool:
        if not meta.match_identifier(identifier=identifier):
            raise AssertionError('meta not match ID: %s' % identifier)
        return self.__meta_table.save_meta(meta=meta, identifier=identifier)

    # Override
    def meta(self, identifier: ID) -> Optional[Meta]:
        return self.__meta_table.meta(identifier=identifier)

    """
        Document for Accounts
        ~~~~~~~~~~~~~~~~~~~~~

        file path: '.dim/public/{ADDRESS}/profile.js'
        redis key: 'mkm.document.{ID}'
        redis key: 'mkm.docs.keys'
    """

    # Override
    def save_document(self, document: Document) -> bool:
        # check with meta first
        meta = self.meta(identifier=document.identifier)
        assert meta is not None, 'meta not exists: %s' % document
        # check document valid before saving it
        if document.valid or document.verify(public_key=meta.public_key):
            return self.__document_table.save_document(document=document)

    # Override
    def documents(self, identifier: ID) -> List[Document]:
        return self.__document_table.documents(identifier=identifier)

    """
        User contacts
        ~~~~~~~~~~~~~

        file path: '.dim/protected/{ADDRESS}/contacts.txt'
        redis key: 'mkm.user.{ID}.contacts'
    """

    # Override
    def local_users(self) -> List[ID]:
        return self.__users

    # Override
    def save_local_users(self, users: List[ID]) -> bool:
        self.__users = users
        return True

    # Override
    def add_user(self, user: ID) -> bool:
        array = self.local_users()
        if user in array:
            # self.warning(msg='user exists: %s, %s' % (user, array))
            return True
        array.insert(0, user)
        return self.save_local_users(users=array)

    # Override
    def remove_user(self, user: ID) -> bool:
        array = self.local_users()
        if user not in array:
            # self.warning(msg='user not exists: %s, %s' % (user, array))
            return True
        array.remove(user)
        return self.save_local_users(users=array)

    # Override
    def current_user(self) -> Optional[ID]:
        array = self.local_users()
        if len(array) > 0:
            return array[0]

    # Override
    def set_current_user(self, user: ID) -> bool:
        array = self.local_users()
        if user in array:
            index = array.index(user)
            if index == 0:
                # self.warning(msg='current user not changed: %s, %s' % (user, array))
                return True
            array.pop(index)
        array.insert(0, user)
        return self.save_local_users(users=array)

    # Override
    def save_contacts(self, contacts: List[ID], user: ID) -> bool:
        self.__contacts[user] = contacts
        return True

    # Override
    def contacts(self, user: ID) -> List[ID]:
        array = self.__contacts.get(user)
        if array is None:
            array = []
            self.__contacts[user] = array
        return array

    # Override
    def add_contact(self, contact: ID, user: ID) -> bool:
        array = self.contacts(user=user)
        if contact in array:
            # self.warning(msg='contact exists: %s, user: %s' % (contact, user))
            return True
        array.append(contact)
        return self.save_contacts(contacts=array, user=user)

    # Override
    def remove_contact(self, contact: ID, user: ID) -> bool:
        array = self.contacts(user=user)
        if contact not in array:
            # self.warning(msg='contact not exists: %s, user: %s' % (contact, user))
            return True
        array.remove(contact)
        return self.save_contacts(contacts=array, user=user)

    """
        Group members
        ~~~~~~~~~~~~~

        file path: '.dim/protected/{ADDRESS}/members.txt'
        redis key: 'mkm.group.{ID}.members'
    """

    # Override
    def founder(self, group: ID) -> Optional[ID]:
        return self.__group_table.founder(group=group)

    # Override
    def owner(self, group: ID) -> Optional[ID]:
        return self.__group_table.owner(group=group)

    # Override
    def members(self, group: ID) -> List[ID]:
        return self.__group_table.members(group=group)

    # Override
    def save_members(self, members: List[ID], group: ID) -> bool:
        return self.__group_table.save_members(members=members, group=group)

    # Override
    def assistants(self, group: ID) -> List[ID]:
        return self.__group_table.assistants(group=group)

    # Override
    def save_assistants(self, assistants: List[ID], group: ID) -> bool:
        return self.__group_table.save_assistants(assistants=assistants, group=group)

    # Override
    def administrators(self, group: ID) -> List[ID]:
        return self.__group_table.administrators(group=group)

    # Override
    def save_administrators(self, administrators: List[ID], group: ID) -> bool:
        return self.__group_table.save_administrators(administrators=administrators, group=group)

    #
    #   Group History DBI
    #

    # Override
    def save_group_history(self, group: ID, content: GroupCommand, message: ReliableMessage) -> bool:
        return self.__history_table.save_group_history(group=group, content=content, message=message)

    # Override
    def group_histories(self, group: ID) -> List[Tuple[GroupCommand, ReliableMessage]]:
        return self.__history_table.group_histories(group=group)

    # Override
    def reset_command_message(self, group: ID) -> Tuple[Optional[ResetCommand], Optional[ReliableMessage]]:
        return self.__history_table.reset_command_message(group=group)

    # Override
    def clear_group_member_histories(self, group: ID) -> bool:
        return self.__history_table.clear_group_member_histories(group=group)

    # Override
    def clear_group_admin_histories(self, group: ID) -> bool:
        return self.__history_table.clear_group_admin_histories(group=group)

    """
        Reliable message for Receivers
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        redis key: 'dkd.msg.{ID}.{sig}'
        redis key: 'dkd.msg.{ID}.messages'
    """

    # Override
    def reliable_messages(self, receiver: ID, limit: int = 1024) -> List[ReliableMessage]:
        # TODO: get cached reliable messages
        return []

    # Override
    def cache_reliable_message(self, msg: ReliableMessage, receiver: ID) -> bool:
        # TODO: cache reliable messages
        return True

    # Override
    def remove_reliable_message(self, msg: ReliableMessage, receiver: ID) -> bool:
        # TODO: remove sent reliable message
        return True

    """
        Group Inbox
        ~~~~~~~~~~~
        
        redis key: 'dkd.grp_msg.{ID}.{sig}'
        redis key: 'dkd.grp_msg.{ID}.messages'
    """

    def inbox_reliable_messages(self, receiver: ID, limit: int = 1024) -> List[ReliableMessage]:
        return self.__inbox_table.reliable_messages(receiver=receiver, limit=limit)

    def inbox_cache_reliable_message(self, msg: ReliableMessage, receiver: ID) -> bool:
        return self.__inbox_table.cache_reliable_message(msg=msg, receiver=receiver)

    def inbox_remove_reliable_message(self, msg: ReliableMessage, receiver: ID) -> bool:
        return self.__inbox_table.remove_reliable_message(msg=msg, receiver=receiver)

    """
        Message Keys
        ~~~~~~~~~~~~

        redis key: 'dkd.key.{sender}'
    """

    # Override
    def cipher_key(self, sender: ID, receiver: ID, generate: bool = False) -> Optional[SymmetricKey]:
        return self.__cipherkey_table.cipher_key(sender=sender, receiver=receiver, generate=generate)

    # Override
    def cache_cipher_key(self, key: SymmetricKey, sender: ID, receiver: ID):
        return self.__cipherkey_table.cache_cipher_key(key=key, sender=sender, receiver=receiver)

    # Override
    def group_keys(self, group: ID, sender: ID) -> Optional[Dict[str, str]]:
        return self.__grp_keys_table.group_keys(group=group, sender=sender)

    # Override
    def save_group_keys(self, group: ID, sender: ID, keys: Dict[str, str]) -> bool:
        return self.__grp_keys_table.save_group_keys(group=group, sender=sender, keys=keys)

    # """
    #     Address Name Service
    #     ~~~~~~~~~~~~~~~~~~~~
    #
    #     file path: '.dim/ans.txt'
    #     redis key: 'dim.ans'
    # """
    #
    # def ans_save_record(self, name: str, identifier: ID) -> bool:
    #     return self.__ans_table.save_record(name=name, identifier=identifier)
    #
    # def ans_record(self, name: str) -> ID:
    #     return self.__ans_table.record(name=name)
    #
    # def ans_names(self, identifier: ID) -> Set[str]:
    #     return self.__ans_table.names(identifier=identifier)

    """
        Login Info
        ~~~~~~~~~~

        redis key: 'mkm.user.{ID}.login'
    """

    # Override
    def login_command_message(self, user: ID) -> Tuple[Optional[LoginCommand], Optional[ReliableMessage]]:
        # TODO: get login command & messages
        return None, None

    # Override
    def save_login_command_message(self, user: ID, content: LoginCommand, msg: ReliableMessage) -> bool:
        # TODO: save login command & messages
        return True

    #
    #   Provider DBI
    #

    # Override
    def all_providers(self) -> List[ProviderInfo]:
        """ get list of (SP_ID, chosen) """
        return [ProviderInfo.GSP]

    # Override
    def add_provider(self, identifier: ID, chosen: int = 0) -> bool:
        # TODO: get ISP
        return True

    # Override
    def update_provider(self, identifier: ID, chosen: int) -> bool:
        # TODO: update ISP
        return True

    # Override
    def remove_provider(self, identifier: ID) -> bool:
        # TODO: remove ISP
        return True

    # Override
    def all_stations(self, provider: ID) -> List[StationInfo]:
        """ get list of (host, port, SP_ID, chosen) """
        # TODO: get stations of ISP
        return []

    # Override
    def add_station(self, identifier: Optional[ID], host: str, port: int, provider: ID, chosen: int = 0) -> bool:
        # TODO: add station for ISP
        return True

    # Override
    def update_station(self, identifier: Optional[ID], host: str, port: int, provider: ID, chosen: int = None) -> bool:
        # TODO: update station for ISP
        return True

    # Override
    def remove_station(self, host: str, port: int, provider: ID) -> bool:
        # TODO: remove station for ISP
        return True

    # Override
    def remove_stations(self, provider: ID) -> bool:
        # TODO: remove all stations for ISP
        return True
