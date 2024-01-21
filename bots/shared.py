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
import threading
from typing import Optional

from dimples import ID
from dimples import Station
from dimples import CommonFacebook
from dimples import AccountDBI, MessageDBI, SessionDBI
from dimples.utils import Config
from dimples.common import ProviderInfo
from dimples.database import Storage
from dimples.client import ClientArchivist, ClientFacebook

from libs.utils import Singleton
from libs.database import Database
from libs.client import Terminal
from libs.client import ClientSession, ClientMessenger
from libs.client import ClientProcessor, ClientPacker
from libs.client import Emitter
from libs.client import SharedGroupManager


@Singleton
class GlobalVariable:

    def __init__(self):
        super().__init__()
        self.config: Optional[Config] = None
        self.adb: Optional[AccountDBI] = None
        self.mdb: Optional[MessageDBI] = None
        self.sdb: Optional[SessionDBI] = None
        self.database: Optional[Database] = None
        self.facebook: Optional[CommonFacebook] = None


def show_help(cmd: str, app_name: str, default_config: str):
    print('')
    print('    %s' % app_name)
    print('')
    print('usages:')
    print('    %s [--config=<FILE>] [BID]' % cmd)
    print('    %s [-h|--help]' % cmd)
    print('')
    print('optional arguments:')
    print('    --config        config file path (default: "%s")' % default_config)
    print('    --help, -h      show this help message and exit')
    print('')


def create_config(app_name: str, default_config: str) -> Config:
    """ Step 1: load config """
    cmd = sys.argv[0]
    try:
        opts, args = getopt.getopt(args=sys.argv[1:],
                                   shortopts='hf:',
                                   longopts=['help', 'config='])
    except getopt.GetoptError:
        show_help(cmd=cmd, app_name=app_name, default_config=default_config)
        sys.exit(1)
    # check options
    ini_file = None
    for opt, arg in opts:
        if opt == '--config':
            ini_file = arg
        else:
            show_help(cmd=cmd, app_name=app_name, default_config=default_config)
            sys.exit(0)
    # check config filepath
    if ini_file is None:
        ini_file = default_config
    if not Storage.exists(path=ini_file):
        show_help(cmd=cmd, app_name=app_name, default_config=default_config)
        print('')
        print('!!! config file not exists: %s' % ini_file)
        print('')
        sys.exit(0)
    # load config from file
    config = Config.load(file=ini_file)
    print('>>> config loaded: %s => %s' % (ini_file, config))
    # check arguments for Bot ID
    if len(args) == 1:
        identifier = ID.parse(identifier=args[0])
        if identifier is None:
            show_help(cmd=cmd, app_name=app_name, default_config=default_config)
            print('')
            print('!!! Bot ID error: %s' % args[0])
            print('')
            sys.exit(0)
        # set bot ID into config['bot']['id']
        bot = config.get('bot')
        if bot is None:
            bot = {}
            config['bot'] = bot
        bot['id'] = str(identifier)
    # OK
    return config


def create_database(config: Config) -> Database:
    """ Step 2: create database """
    root = config.database_root
    public = config.database_public
    private = config.database_private
    # create database
    db = Database(root=root, public=public, private=private)
    db.show_info()
    # default provider
    provider = ProviderInfo.GSP
    # add neighbors
    neighbors = config.neighbors
    for node in neighbors:
        print('adding neighbor node: %s' % node)
        db.add_station(identifier=None, host=node.host, port=node.port, provider=provider)
    return db


def create_facebook(database: AccountDBI, current_user: ID) -> CommonFacebook:
    """ Step 3: create facebook """
    facebook = ClientFacebook()
    # create archivist for facebook
    archivist = ClientArchivist(database=database)
    archivist.facebook = facebook
    facebook.archivist = archivist
    # make sure private key exists
    sign_key = facebook.private_key_for_visa_signature(identifier=current_user)
    msg_keys = facebook.private_keys_for_decryption(identifier=current_user)
    assert sign_key is not None, 'failed to get sign key for current user: %s' % current_user
    assert msg_keys is not None and len(msg_keys) > 0, 'failed to get msg keys: %s' % current_user
    print('set current user: %s' % current_user)
    facebook.current_user = facebook.user(identifier=current_user)
    # set for group manager
    g_man = SharedGroupManager()
    g_man.facebook = facebook
    return facebook


def create_session(facebook: CommonFacebook, database: SessionDBI, host: str, port: int) -> ClientSession:
    # 1. create station with remote host & port
    station = Station(host=host, port=port)
    station.data_source = facebook
    # 2. create session with SessionDB
    session = ClientSession(station=station, database=database)
    # 3. set current user
    user = facebook.current_user
    session.set_identifier(identifier=user.identifier)
    return session


def create_messenger(facebook: CommonFacebook, database: MessageDBI,
                     session: ClientSession, processor_class) -> ClientMessenger:
    assert issubclass(processor_class, ClientProcessor), 'processor class error: %s' % processor_class
    # 1. create messenger with session and MessageDB
    messenger = ClientMessenger(session=session, facebook=facebook, database=database)
    # 2. create packer, processor for messenger
    #    they have weak references to facebook & messenger
    messenger.packer = ClientPacker(facebook=facebook, messenger=messenger)
    messenger.processor = processor_class(facebook=facebook, messenger=messenger)
    # 3. set weak reference to messenger
    session.messenger = messenger
    # set for group manager
    g_man = SharedGroupManager()
    g_man.messenger = messenger
    return messenger


#
#   DIM Bot
#


def check_bot_id(config: Config, ans_name: str) -> bool:
    identifier = config.get_identifier(section='bot', option='id')
    if identifier is not None:
        # got it
        return True
    identifier = config.get_identifier(section='ans', option=ans_name)
    if identifier is None:
        # failed to get Bot ID
        return False
    bot_sec = config.get('bot')
    if bot_sec is None:
        bot_sec = {}
        config['bot'] = bot_sec
    bot_sec['id'] = str(identifier)
    return True


def start_bot(default_config: str, app_name: str, ans_name: str, processor_class) -> Terminal:
    # create global variable
    shared = GlobalVariable()
    # Step 1: load config
    config = create_config(app_name=app_name, default_config=default_config)
    shared.config = config
    if not check_bot_id(config=config, ans_name=ans_name):
        raise LookupError('Failed to get Bot ID: %s' % config)
    # Step 2: create database
    db = create_database(config=config)
    shared.adb = db
    shared.mdb = db
    shared.sdb = db
    shared.database = db
    # Step 3: create facebook
    bid = config.get_identifier(section='bot', option='id')
    facebook = create_facebook(database=db, current_user=bid)
    shared.facebook = facebook
    # create session for messenger
    host = config.station_host
    port = config.station_port
    session = create_session(facebook=facebook, database=db, host=host, port=port)
    messenger = create_messenger(facebook=facebook, database=db, session=session, processor_class=processor_class)
    facebook.archivist.messenger = messenger
    # set messenger to emitter
    emitter = Emitter()
    emitter.messenger = messenger
    # create & start terminal
    terminal = Terminal(messenger=messenger)
    thread = threading.Thread(target=terminal.run, daemon=False)
    thread.start()
    return terminal
