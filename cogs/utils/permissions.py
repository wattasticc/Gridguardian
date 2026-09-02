from discord.ext import commands


def is_admin():
    return commands.has_permissions(administrator=True)


def can_moderate():
    return commands.has_permissions(
        ban_members=True,
        kick_members=True,
        moderate_members=True
    )


def manage_server():
    return commands.has_permissions(manage_guild=True)