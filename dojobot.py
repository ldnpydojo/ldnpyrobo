# coding: utf-8
import os
import dbm
from itertools import cycle
import asyncio

import discord
import github


NUM_TEAMS = 5
TEAMS = range(1, NUM_TEAMS + 1)

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
DISCORD_SECRET = os.environ['DISCORD_SECRET']

next_team = cycle(TEAMS)

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
    if len(args) != 2 or args[0] != 'github':
        await reply("You should type `!register github <account>`")

    author = message.author
    channel = message.channel
    guild = message.guild
    account = args[1]
    team = assign_team(str(author))
    repo = 'lordmauve/tetrish'

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
