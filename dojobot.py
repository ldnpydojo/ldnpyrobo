# coding: utf-8
import os
import dbm
from itertools import cycle
import asyncio
from pathlib import Path
import json

import discord
import github


def set_num_teams(n):
    global NUM_TEAMS, TEAMS, next_team
    
    NUM_TEAMS = 5
    TEAMS = range(1, NUM_TEAMS + 1)
    next_team = cycle(TEAMS)
    
    
set_num_teams(5)

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
DISCORD_SECRET = os.environ['DISCORD_SECRET']
ADMIN_ROLE = 704428302420541441

config_file = Path(__file__).with_name('config.json')

config = json.loads(config_file.read_text())
db = dbm.open('teams.db', 'c')

teams = {num: [] for num in TEAMS}
client = discord.Client()
gh = github.Github(GITHUB_TOKEN)


def assign_team(username: str) -> int:
    """Assign a user to a team.

    The result is stored in the database so that the user will be assigned
    to the same team if they register again.
    """
    try:
        return int(db[username])
    except KeyError:
        team = next(next_team)
        db[username] = str(team)
        return team


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


HANDLERS = {}


def command(func):
    """Decorator to register a function as a handler for a command."""
    HANDLERS[func.__name__] = func
    return func


def invite_to_github_repo(username: str, repo_name: str) -> bool:
    """Invite a user to a GitHub repo."""
    repo = gh.get_repo(repo_name, lazy=True)
    try:
        repo.add_to_collaborators(username, 'push')
    except Exception:
        import traceback
        traceback.print_exc()
        return False
    return True


async def grant_role(guild, member, role_name) -> bool:
    """Grant a Discord role to a user."""
    roles = {r.name: r for r in guild.roles}
    if role_name not in roles:
        return False
    await member.add_roles(
        roles[role_name],
        reason=f"Assigned to {role_name} by bot"
    )
    return True


@command
async def register(*args, message):
    """Register for the dojo using your GitHub username."""
    if len(args) != 2 or args[0] != 'github':
        await reply("You should type `!register github <account>`")

    author = message.author
    channel = message.channel
    guild = message.guild
    account = args[1]
    team = assign_team(str(author))
    
    prefix = config['repo_prefix']
    repo = f'{prefix}{team}'

    loop = asyncio.get_running_loop()

    async with channel.typing():
        invited, granted = await asyncio.gather(
            loop.run_in_executor(
                None,
                invite_to_github_repo,
                account,
                repo
            ),
            grant_role(guild, author, f'Team {team}')
        )
        msgs = [f"<@{author.id}>: You are on team {team}."]
        if invited:
            msgs.append(f"I have invited you to https://github.com/{repo}.")
        else:
            msgs.append(f"Something went wrong when adding you to the repo.")
        if granted:
            msgs.append(f"You now have access to the team {team} channels.")
        await channel.send('\n\n'.join(msgs))
        

@command
async def roles(*args, message):
    """Print the roles you are a member of."""
    author = message.author
    roles = author.roles
    await message.channel.send(
        f"<@{author.id}> Your roles: " + ' '.join(f"{role.name}'" for role in roles)
    )
    
    
def is_herder(member):
    """Return True if the user is a cat herder."""
    return any(r.id == ADMIN_ROLE for r in member.roles)


@command
async def teams(*args, message):
    """Set the number of teams."""
    author = message.author
    if not is_herder(author):
        await message.channel.send(f"<@{author.id}> You are not a cat herder.")
        return
    
    try:
        num, = map(int, args)
    except Exception:
        await message.channel.send("Usage: !teams <num>")
        
    set_num_teams(num)
    for k in list(db.keys()):
        del db[k]
    await message.channel.send(f"Set to {num} teams.")
        
        
@command
async def help(*args, message):
    """Show this help."""
    help_text = '\n'.join(
        f'{k:<10} {v.__doc__}'
        for k, v in HANDLERS.items()
    )
    await message.channel.send(help_text)
        
        
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if not message.content.startswith('!'):
        return

    command, *args = message.content.split()

    try:
        handler = HANDLERS[command.lstrip('!')]
    except KeyError:
        await message.channel.send(f"I don't know the command {command}")
    else:
        try:
            await handler(
                *args,
                message=message,
            )
        except Exception:
            import traceback
            traceback.print_exc()
            await message.channel.send(f"```{traceback.format_exc()}\n```")


client.run(DISCORD_SECRET)
