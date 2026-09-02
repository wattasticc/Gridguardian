import discord

from utils.colors import GRID_BLUE


def create_embed(
    title: str,
    description: str | None = None,
    *,
    thumbnail: str | None = None,
    image: str | None = None,
    author_name: str | None = None,
    author_icon: str | None = None,
):
    """
    Creates a Grid Guardian styled embed.
    """

    embed = discord.Embed(
        title=title,
        description=description,
        color=GRID_BLUE,
        timestamp=discord.utils.utcnow()
    )

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    if image:
        embed.set_image(url=image)

    if author_name:
        embed.set_author(
            name=author_name,
            icon_url=author_icon if author_icon else discord.Embed.Empty
        )

    embed.set_footer(
        text="⚡ Grid Guardian • Apex Legends Community Bot"
    )

    return embed