import discord
from discord.ext import tasks
from env import ENV
import logging
import re
import datetime
import pytz
import json
import os.path
import asyncio

logging.basicConfig(level=logging.INFO)
client = discord.Client()

# CONSTANTS
time_newlist = (0, 5) # 00:01
newlist_schedule_running = False
timezone = pytz.timezone("Europe/Riga")

cm_help = "help"
cm_channel = "channel"
cm_prefix = "prefix"
cm_new_list = "newlist"
cm_message = "message"
cm_schedule = "schedule"
cm_stop_schedule = "unschedule"

reaction_list = ['📘', '📗', '📙', '📕', '📚']

read_description_by_level = {
    0: 'picked up a book',
    1: 'read for 15 to 29 minutes',
    2: 'read for 30 to 59 minutes',
    3: 'read for 1h to 1h 29m',
    4: 'read for 1h 30m or more 🤓'
}

# SAVEABLE VARIABLES

# load savedata if it exists
packed_savedata = None
save_file_name = "savefile.json"
if (os.path.isfile(save_file_name)):
    with open(save_file_name, 'r') as f:
        packed_savedata = json.loads(f.read())

# this will be fetched when client starts
prefix = "bc!"
working_channel = 0
embed_message = None
read_list = []

# AUXILIARY FUNCTIONS
def is_on_read_list(lst, user):
    def is_the_user(u):
        return u[0] == user
    
    return len(list(filter(is_the_user, lst))) > 0

def previous_reaction_of_user(lst, user):
    def is_the_user(u):
        return u[0] == user
    
    return list(filter(is_the_user, lst))[0][1]

async def send_embed():
    global embed_message
    read_list_str = ""
    empty_list_sad = "no one yet :("
    description_str = "**Did you a read a book today? React accordingly:**\n"
    for i in range(len(reaction_list)):
        description_str += f'{reaction_list[i]} - {read_description_by_level[i]}\n'

    for user_tuple in read_list:
        read_list_str += f"• <@{user_tuple[0]}>: {read_description_by_level[user_tuple[1]]}\n"

    embed = discord.Embed(
        title=f"{get_time_now().strftime('%Y/%m/%d')} Book Club Accountability List",
        description=description_str, color=0x8332a8)

    if (embed_message != None):
        if (read_list_str == ""):
            embed.add_field(name="Cuties that read a book today:", value=empty_list_sad, inline=False)
        else:
            embed.add_field(name="Cuties that read a book today:", value=read_list_str, inline=False)
        await embed_message.edit(embed=embed)
    else:
        embed.add_field(name="Cuties that read a book today:", value=empty_list_sad, inline=False)
        channel = client.get_channel(working_channel)
        embed_message = await channel.send(embed=embed)
        for emoji in reaction_list:
            await embed_message.add_reaction(emoji)
    
    save_data()

async def send_help(channel):
    help_message_str = f'`{prefix}{cm_new_list}` - start a new book club list (you should probably pin it)\n'
    help_message_str += f'`{prefix}{cm_channel} <channel>` - change the channel that I\'ll listen for commands in\n'
    help_message_str += f'`{prefix}{cm_prefix} <prefix>` - change the prefix from {prefix} to something else\n'
    help_message_str += f'`{prefix}{cm_schedule} <hh:mm>` - schedule a time to send a new list everyday\n'
    help_message_str += f'`{prefix}{cm_stop_schedule}` - stop sending a new list everyday\n'
    help_message_str += f'`{prefix}{cm_help}` - the command you just used\n'
    help_message_str += f'`{prefix}{cm_message}` - I send a nice message for these trying times'
    await channel.send(help_message_str)

def save_data():
    global packed_savedata

    packed_savedata = (
        prefix,
        working_channel,
        embed_message.id,
        read_list
    )

    with open(save_file_name, 'w') as f:
        f.write(json.dumps(packed_savedata))
    
    print('data saved')

def get_time_now():
    utc_now = pytz.utc.localize(datetime.datetime.utcnow())
    now_riga = utc_now.astimezone(timezone)
    return now_riga

def seconds_until(hours, minutes):
    given_time = datetime.time(hours, minutes)
    now = get_time_now()
    future_exec = timezone.localize(datetime.datetime.combine(now, given_time))

    if (future_exec - now).days < 0:  # If we are past the execution, it will take place tomorrow
        future_exec = timezone.localize(datetime.datetime.combine(now + datetime.timedelta(days=1), given_time)) # days always >= 0

    return (future_exec - now).total_seconds()
    
async def send_newlist_at_right_time():
    global read_list
    global embed_message

    while newlist_schedule_running:
        # Will stay here until clock is at right time
        await asyncio.sleep(seconds_until(time_newlist[0], time_newlist[1]))

        # Accounts for when cm_stop_schedule was called while the previous waiting
        if (newlist_schedule_running):
            read_list = []
            embed_message = None
            await send_embed()

            # Ensures that this isn't spammed for a minute
            await asyncio.sleep(60)

# DISCORD LISTENER FUNCTIONS

@client.event
async def on_ready():
    global prefix
    global working_channel
    global embed_message
    global read_list
    global newlist_schedule_running

    # unpack the savedata or set defaults
    if (packed_savedata != None):
        prefix, working_channel, embed_message_id, read_list = packed_savedata
        fetched_channel = await client.fetch_channel(working_channel)
        embed_message = await fetched_channel.fetch_message(embed_message_id)
        print(read_list)
        print('data loaded')
    
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    global prefix
    global working_channel
    global participating_userlist
    global read_list
    global embed_message
    global newlist_schedule_running
    global time_newlist

    if message.author == client.user:
        return

    # allow a few commands with tagging
    if message.content.startswith('<@'):
        regex_usertag = re.compile('<\@!([0-9]*)>')
        matched = regex_usertag.match(message.content)
        if (matched.group(1) == str(client.user.id)):
            arguments = message.content.split(' ')[1:]

            # help command
            if (arguments[0] == cm_help):
                await send_help(message.channel)
            
            # prefix command
            elif (arguments[0] == cm_prefix):
                if (len(arguments) < 2):
                    await message.channel.send(f'this is how you use this command, sweetheart: \'<@!{client.user.id}> {cm_prefix} <new prefix>\'')
                else:
                    prefix = arguments[1]
                    await message.channel.send(f'prefix changed to {prefix}')
                    save_data()

    # normal commands, with prefix
    elif message.content.startswith(prefix):
        command = message.content.replace(prefix, '', 1).split(' ')[0]
        arguments = message.content.split(' ')[1:]

        # always can change prefix
        if (command == cm_prefix):
            if (len(arguments) > 0):
                prefix = arguments[0]
                await message.channel.send(f'prefix changed to {prefix}')
                save_data()
            else:
                await message.channel.send(f'this is how you use this command, sweetheart: `{prefix}{cm_prefix} <new prefix>`')

        # first thing is set a working channel
        elif (working_channel == 0):
            if (command != cm_channel):
                await message.channel.send(f"what do you think you are doing?? first thing you have to do is setup a channel for me to use, using `{prefix}{cm_channel} #channel`")
            else:
                regex_channel = re.compile('<#([0-9]*)>')
                matched = regex_channel.match(arguments[0])
                if (matched != None):
                    changed_channel_id = matched.group(1)
                    working_channel = int(changed_channel_id)
                    await message.channel.send(f'from now on I\'ll only work on <#{changed_channel_id}> :D')
                    save_data()
                else:
                    await message.channel.send(f'this is how you use this command, sweetheart: `{prefix}{cm_channel} <channel>`')

        # working channel is set, can do other things
        else:

            # send a new embed, starting a new list
            if (command == cm_new_list):
                # has to be mod to use
                if (message.author.permissions_in(message.channel).manage_channels):
                    read_list = []
                    embed_message = None
                    await send_embed()
                else:
                    await message.channel.send(f'you don\'t have permission for that \'-\'')
            
            # help command
            elif (command == cm_help):
                await send_help(message.channel)
            
            # easter egg
            elif (command == cm_message):
                await message.channel.send(f'suicide squad 2 > twilight :D')
            
            # schedule to send new list at a certain time
            elif (command == cm_schedule):
                # has to be mod to use
                if (message.author.permissions_in(message.channel).manage_channels):
                    regex_channel = re.compile('([0-9][0-9]:[0-9][0-9])')
                    if (len(arguments) < 1):
                        await message.channel.send(f'this is how you use this command, sweetheart: `{prefix}{cm_schedule} hh:mm` using the 24 hours format')
                    else:
                        matched = regex_channel.match(arguments[0])
                        if (matched != None):
                            hours = int(matched.group(1).split(':')[0])
                            minutes = int(matched.group(1).split(':')[1])

                            time_newlist = (hours, minutes)

                            newlist_schedule_running = True
                            await message.channel.send(f'I will send a new list everyday at {matched.group(1)} Riga time :D')
                            await send_newlist_at_right_time()
                        else:
                            await message.channel.send(f'this is how you use this command, sweetheart: `{prefix}{cm_schedule} hh:mm` using the 24 hours format')
                else:
                    await message.channel.send(f'you don\'t have permission for that \'-\'')
            
            elif (command == cm_stop_schedule):
                if (message.author.permissions_in(message.channel).manage_channels):
                    if (newlist_schedule_running):
                        newlist_schedule_running = False
                        await message.channel.send(f'I will stop sending a new list everyday, I hope you know what you\'re doing lol')
                    else:
                        await message.channel.send(f'I\'m not even scheduled to send lists everyday 🤔')
                else:
                    await message.channel.send(f'you don\'t have permission for that \'-\'')
            
# reaction added on any message
@client.event
async def on_raw_reaction_add(payload):
    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    # is a react in the list
    if (embed_message != None and payload.message_id == embed_message.id and (not payload.user_id == client.user.id)):

        # is one of the supported emojis
        if (payload.emoji.name in reaction_list):

            # user already reacted
            if (is_on_read_list(read_list, payload.user_id)):
                previous_emoji = previous_reaction_of_user(read_list, payload.user_id)
                await message.remove_reaction(reaction_list[previous_emoji], payload.member)
            
            read_list.append((payload.user_id, reaction_list.index(payload.emoji.name)))
            await send_embed()

# reaction removed on any message
@client.event
async def on_raw_reaction_remove(payload):
    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    # is a react in the list
    if (payload.message_id == embed_message.id):

        # is one of the supported emojis
        if (payload.emoji.name in reaction_list):
            try:
                read_list.remove((payload.user_id, reaction_list.index(payload.emoji.name)))
            except ValueError:
                read_list.remove([payload.user_id, reaction_list.index(payload.emoji.name)])
            await send_embed()

client.run(ENV['token'])