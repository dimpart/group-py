# DIM Group Assistant Bot (Python)

DIM group is decentralized, there's no central database to store the membership, so we need a consensus mechanism to manage it.

Here I designed a group bot ```assistant``` for maintaining the group information (group name, founder, owner, members, administrators, assistants, etc...),
and serving the members to split and redirect group messages.

## Bulletin (Group Document)

The bulletin is a document for group, which has a JsON data includes:

Data Field     | Description
---------------|------------------------------------------------------------------
name           | group title
founder        | group creator
owner          | same as founder in current version
assistants     | modified by founder only
administrators | modified by owner only
created_time   |
modified_time  | (OPTIONAL)

* All the fields above must be set in ```bulletin.data``` and signed by the owner or founder.

The bulletin from the group bot to all members (owner + admins + members) can also have a field in the top level containing group command messages before they have been commited by the owner or any administrator:

Bulletin Field | Description
---------------|------------------------------------------------------------------
resignations   | admin's resign command, or ordinary member's quit command
confirmations  | signatures of resignations to respond to the bot after committed

If the owner received ```resign``` commands in bulletin.resignations, it should update the bulletin and send the new one back to the bot:

```python
	administrator_list = ID.revert(array=new_administrators)
	bulletin.set_property(key="administrators", value=administrator_list);
	bulletin.sign(private_key=private_key);
```

If the owner or any administrator received ```quit``` commands in bulletin.resignnations, they should update member list and send a ```reset``` command back to the bot;

The owner or administrator should remove the committed resignations and put their signatures in ```confirmations``` of new bulletin and send back to the bot.

## Group Commands

Group commands are the special messages for maintaining membership:

* When a stranger want to join the group, a ```join``` command should be sent to all administrators (owner + admins) and wait for review;
* When an ordinary member wanna invite a new member, an ```invite``` command should be sent to all administrators and wait for review;
* When an ordinary member want to quit, a ```quit``` command would be sent to all members (owner + admins + members), and the owner or any administrator should change the member list when they received it;
* When an admin want to resign, a ```resign``` command would be sent to all members, and the owner should change the field ```administrators``` in bulletin.data when it received.

Command Name | Description
-------------|--------------------------------------
found        | create a new group
abdicate     | transfer ownership to another member
**invite**   | add new member(s)
expel        | remove member(s)
**join**     | add myself as new member
**quit**     | remove myself from member list
**reset**    | update member list
**query**    | query member list
hire         | add new administrator(s)
fire         | remove administrator(s)
**resign**   | remove myself from administrator list

Group commands should be a broadcast message with group ID:

```python
	msg.receiver = "members@anywhere";
	msg.group    = group_id;
	msg.data     = plaintext;       # json_encode(group_command_content)
```

it will be sent to the group bot to let it knows the latest membership:

```python
	msg.receiver = bot_id;
	msg.key      = encrypted_key;
	msg.data     = encrypted_data;  # forward command for the broadcast message
```

So the group bot can know which destination they should go,
when the actual recipient online, the bot will redirect the splitted message for it:

```python
	msg.receiver = member_id;
	msg.key      = encrypted_key;
	msg.data     = encrypted_data;  # forward command for the broadcast message
```

Here are the broadcast receivers for group commands:

         | anyone@ | owner@ | members@      | administrators@ | assistants@
---------|---------|--------|---------------|-----------------|-------------
founder  | found   | ?      |               |                 |
owner    | -       | ?      | reset         | -               | query
admin    | -       | -      | reset, resign | -               | query
member   | -       | -      | quit          | invite          | query
stranger | -       | -      | -             | join            | -

* members@anywhere => all members (owner + admins + members)
* administrators@anywhere => all administrators (owner + admins)

## Messaging

While any member wanna send messages in group,
it should generate a symmetric key to encrypt the message content to an encrypted data,
and then encrypt the symmetric key by each member's public key (from visa document);
after that, pack message with the encrypted data and encrypted keys and forward to the group bot:

```python
	msg.receiver = group_id;
	msg.keys     = {...};
	msg.data     = encrypted_data;
```

The group bot will split the group message for all members and cache in their inboxes;
when the receivers online, the bot will redirect the splitted messages for them:

```python
	msg.receiver = member_id;
	msg.group    = group_id;
	msg.key      = encrypted_key;
	msg.data     = encrypted_data;
```

**NOTICE:**
Don't encrypt the symmetric key for the group bot, because the bot should never decrypt the message content!

## Roles Definition

The group assistant is a bot only redirecting message for all group members,
it won't change to a member and should not decrypt group messages.

**Transition Model**

```

        +-----------+                                   +-----------+
        |  Founder  |                                   | Assistant |
        +-----------+                                   +-----------+
            :
            :   ...................       .....................
            :   :                 :       :                   :
            V   :                 V       :                   V
        +-----------+           +-----------+           +-----------+
        |   Owner   |           |  Members  |           | Strangers |
        +-----------+           +-----------+           +-----------+
            A   A                 :  : A  A                   :
            :   :                 :  : :  :                   :
            :   :.................:  : :  :...................:
            :                        : :
            :   +----------------+   : :
            :   | Administrators |   : :
            :   +----------------+   : :
            :       :      : A       : :
            :       :      : :.......: :
            :.......:      :...........:


```

* Any user can generate a group, and it will be the founder automatically;
* The group founder will be the first owner automatically;
* The founder should appoint an assistant (group bot) in the bulletin (group document);
* Any group must/only have an owner (in current version, the group owner is its founder);
* The owner must be at the front of the member list;
* All members can send messages in group;
* All group messages should be encrypted before sending to the bot, the bot is only responsible for splitting and redirecting messages for the members;
* All group commands must be sent to the group assistant to update membership;
* Any member, includes the owner and administrators, should process commands forwarded by the bot to refresh the group's membership;

## Permissions

Group permissions include modifying bulletin and changing membership.

### Bulletin Permissions:

                   | Founder | Owner | Administrators | Members | Assistants (Bots) | Strangers
-------------------|:-------:|:-----:|:--------------:|:-------:|:-----------------:|:---------:
name               | YES     | YES   | -              | -       | -                 | -
founder            | CONST   | -     | -              | -       | -                 | -
owner              | ?       | ?     | -              | -       | -                 | -
assistants         | YES     | -     | -              | -       | -                 | -
admins             | -       | YES   | -              | -       | -                 | -
created time       | CONST   | -     | -              | -       | -                 | -
modified time      | YES     | YES   | -              | -       | -                 | -
*query bulletin*   | *YES*   | *YES* | *YES*          | *YES*   | *YES*             | *YES*

* Only the group founder/owner can modify bulletin.

### Membership Permissions:

                   | Founder | Owner | Administrators | Members | Assistants (Bots) | Strangers
-------------------|:-------:|:-----:|:--------------:|:-------:|:-----------------:|:---------:
change owner       | ?       | ?     | -              | -       | -                 | -
change assistants  | YES     | -     | -              | -       | -                 | -
hire/fire admins   | -       | YES   | -              | -       | -                 | -
resign admin       | -       | -     | YES            | -       | -                 | -
invite members     | -       | YES   | YES            | YES     | -                 | -
review members     | -       | YES   | YES            | -       | -                 | -
expel members      | -       | YES   | YES            | -       | -                 | -
join group         | -       | -     | -              | -       | -                 | YES
quit group         | NEVER   | -     | -              | YES     | -                 | -
*query membership* | *YES*   | *YES* | *YES*          | *YES*   | *YES*             | -

* The group owner/administrators cannot quit until they are retired.
* The group assistants (bots) only redirect messages, cannot modify membership;
* When a stranger want to join the group, or be invited, a command will be sent to the bots, and then redirect to the owner and all administrators;
* The owner or any administrator can review the invite/join application.

----
Albert Moky @ Aug. 15, 2023
