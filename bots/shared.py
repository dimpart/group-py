# -*- coding: utf-8 -*-
# ==============================================================================
# MIT License
#
# Copyright (c) 2022 Albert Moky
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

import getopt
import sys
from typing import Optional

from dimples import ID
from dimples import Document
from dimples import CommonFacebook
from dimples import AccountDBI, MessageDBI, SessionDBI
from dimples.client import ClientChecker

from libs.utils import Singleton, Config, Path
from libs.database import Database

from libs.client import LibraryLoader
from libs.client import ClientArchivist, ClientFacebook
from libs.client import ClientSession, ClientMessenger
from libs.client import Terminal
from libs.client import Emitter
from libs.client import SharedGroupManager
from libs.client import Footprint

from cpu import GroupKeyManager
from cpu import GroupMessageDistributor, GroupMessageHandler


@Singleton
class GlobalVariable:

    def __init__(self):
        super().__init__()
        self.__config: Optional[Config] = None
        self.__adb: Optional[AccountDBI] = None
        self.__mdb: Optional[MessageDBI] = None
        self.__sdb: Optional[SessionDBI] = None
        self.__database: Optional[Database] = None
        self.__facebook: Optional[ClientFacebook] = None
        self.__messenger: Optional[ClientMessenger] = None
        # load extensions
        LibraryLoader().run()

    @property
    def config(self) -> Config:
        return self.__config

    @property
    def adb(self) -> AccountDBI:
        return self.__adb

    @property
    def mdb(self) -> MessageDBI:
        return self.__mdb

    @property
    def sdb(self) -> SessionDBI:
        return self.__sdb

    @property
    def database(self) -> Database:
        return self.__database

    @property
    def facebook(self) -> ClientFacebook:
        return self.__facebook

    @property
    def messenger(self) -> ClientMessenger:
        return self.__messenger

    @messenger.setter
    def messenger(self, transceiver: ClientMessenger):
        self.__messenger = transceiver
        # set for group manager
        man = SharedGroupManager()
        man.messenger = transceiver
        # set for entity checker
        checker = self.facebook.checker
        assert isinstance(checker, ClientChecker), 'entity checker error: %s' % checker
        checker.messenger = transceiver
        # set for emitter
        emitter = Emitter()
        emitter.messenger = transceiver
        # set for group message handlers
        gm_han = GroupMessageHandler()
        gm_dis = GroupMessageDistributor()
        gm_han.messenger = transceiver
        gm_dis.messenger = transceiver

    async def prepare(self, config: Config):
        #
        #  Step 0: load ANS
        #
        ans_records = config.ans_records
        if ans_records is not None:
            # load ANS records from 'config.ini'
            CommonFacebook.ans.fix(records=ans_records)
        self.__config = config
        #
        #  Step 1: create database
        #
        database = await create_database(config=config)
        self.__adb = database
        self.__mdb = database
        self.__sdb = database
        self.__database = database
        #
        #  Step 2: create facebook
        #
        facebook = await create_facebook(database=database)
        self.__facebook = facebook
        #
        #  Step 3
        #
        # set for footprint
        fp = Footprint()
        fp.database = database
        fp.facebook = facebook
        # set for group manager
        g_man = SharedGroupManager()
        g_man.facebook = facebook
        # set for group message handler
        gm_han = GroupMessageHandler()
        gm_han.facebook = facebook
        # set for group message handlers
        gm_dis = GroupMessageDistributor()
        gm_dis.database = database
        # set for group key handler
        key_man = GroupKeyManager()
        key_man.database = database

    async def login(self, current_user: ID):
        facebook = self.facebook
        archivist = facebook.archivist
        # make sure private keys exists
        sign_key = await facebook.private_key_for_visa_signature(identifier=current_user)
        msg_keys = await facebook.private_keys_for_decryption(identifier=current_user)
        assert sign_key is not None, 'failed to get sign key for current user: %s' % current_user
        assert len(msg_keys) > 0, 'failed to get msg keys: %s' % current_user
        print('set current user: %s' % current_user)
        user = await facebook.get_user(identifier=current_user)
        assert user is not None, 'failed to get current user: %s' % current_user
        visa = await user.visa
        if visa is not None:
            # refresh visa
            visa = Document.parse(document=visa.copy_dictionary())
            visa.sign(private_key=sign_key)
            await archivist.save_document(document=visa)
        await facebook.set_current_user(user=user)


async def create_database(config: Config) -> Database:
    """ create database with directories """
    db = Database(config=config)
    db.show_info()
    return db


async def create_facebook(database: AccountDBI) -> CommonFacebook:
    """ create facebook """
    facebook = ClientFacebook(database=database)
    facebook.barrack = ClientArchivist(facebook=facebook, database=database)
    facebook.checker = ClientChecker(facebook=facebook, database=database)
    return facebook


def show_help(app_name: str, default_config: str):
    cmd = sys.argv[0]
    print('')
    print('    %s' % app_name)
    print('')
    print('usages:')
    print('    %s [--config=<FILE>]' % cmd)
    print('    %s [-h|--help]' % cmd)
    print('')
    print('optional arguments:')
    print('    --config        config file path (default: "%s")' % default_config)
    print('    --help, -h      show this help message and exit')
    print('')


async def create_config(app_name: str, default_config: str) -> Config:
    """ load config """
    try:
        opts, args = getopt.getopt(args=sys.argv[1:],
                                   shortopts='hf:',
                                   longopts=['help', 'config='])
    except getopt.GetoptError:
        show_help(app_name=app_name, default_config=default_config)
        sys.exit(1)
    # check options
    ini_file = None
    for opt, arg in opts:
        if opt == '--config':
            ini_file = arg
        else:
            show_help(app_name=app_name, default_config=default_config)
            sys.exit(0)
    # check config filepath
    if ini_file is None:
        ini_file = default_config
    if not await Path.exists(path=ini_file):
        show_help(app_name=app_name, default_config=default_config)
        print('')
        print('!!! config file not exists: %s' % ini_file)
        print('')
        sys.exit(0)
    # load config from file
    config = Config()
    await config.load(path=ini_file)
    print('>>> config loaded: %s => %s' % (ini_file, config))
    return config


#
#   DIM Bot
#


async def start_bot(ans_name: str, processor_class) -> Terminal:
    shared = GlobalVariable()
    config = shared.config
    bot_id = config.get_identifier(section='ans', option=ans_name)
    bot_id = ID.parse(bot_id)
    assert bot_id is not None, 'Failed to get Bot ID: %s' % config
    await shared.login(current_user=bot_id)
    # create terminal
    host = config.station_host
    port = config.station_port
    assert host is not None and port > 0, 'station config error: %s' % config
    client = BotClient(facebook=shared.facebook, database=shared.sdb, processor_class=processor_class)
    await client.connect(host=host, port=port)
    await client.run()
    return client


class BotClient(Terminal):

    def __init__(self, facebook: ClientFacebook, database: SessionDBI, processor_class):
        super().__init__(facebook=facebook, database=database)
        self.__processor_class = processor_class

    # Override
    def _create_processor(self, facebook: ClientFacebook, messenger: ClientMessenger):
        return self.__processor_class(facebook, messenger)

    # Override
    def _create_messenger(self, facebook: ClientFacebook, session: ClientSession) -> ClientMessenger:
        shared = GlobalVariable()
        messenger = ClientMessenger(session=session, facebook=facebook, database=shared.mdb)
        shared.messenger = messenger
        return messenger
