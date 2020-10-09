import io
import traceback
import typing

import aiohttp
import discord
from discord.ext import commands

from . import utils


class ErrorHandler(utils.Cog):

    COMMAND_ERROR_RESPONSES = (
        (
            utils.errors.MissingRequiredArgumentString,
            lambda ctx, error: f"You're missing the `{error.param}` argument, which is required for this command - see `{ctx.clean_prefix}help {ctx.command.name}`."
        ),
        (
            commands.MissingRequiredArgument,
            lambda ctx, error: f"You're missing the `{error.param.name}` argument, which is required for this command - see `{ctx.clean_prefix}help {ctx.command.name}`."
        ),
        (
            (commands.UnexpectedQuoteError, commands.InvalidEndOfQuotedStringError, commands.ExpectedClosingQuoteError),
            lambda ctx, error: "The quotes in your message have been done incorrectly."
        ),
        (
            commands.CommandOnCooldown,
            lambda ctx, error: f"You can't use this command again for another {utils.TimeValue(error.retry_after).clean_spaced}."
        ),
        (
            commands.NSFWChannelRequired,
            lambda ctx, error: "This command can't be run in a non-NSFW channel."
        ),
        (
            commands.DisabledCommand,
            lambda ctx, error: "This command has been disabled."
        ),
        (
            commands.MissingAnyRole,
            lambda ctx, error: f"You need to have one of the {', '.join(['`' + i + '`' for i in error.missing_roles])} roles to be able to run this command."
        ),
        (
            commands.BotMissingAnyRole,
            lambda ctx, error: f"I need to have one of the {', '.join(['`' + i + '`' for i in error.missing_roles])} roles for you to be able to run this command."
        ),
        (
            commands.MissingRole,
            lambda ctx, error: f"You need to have the `{error.missing_role}` role to be able to run this command."
        ),
        (
            commands.BotMissingRole,
            lambda ctx, error: f"I need to have the `{error.missing_role}` role for you to be able to run this command."
        ),
        (
            commands.MissingPermissions,
            lambda ctx, error: f"You need the `{error.missing_perms[0]}` permission to run this command."
        ),
        (
            commands.BotMissingPermissions,
            lambda ctx, error: f"I need the `{error.missing_perms[0]}` permission for me to be able to run this command."
        ),
        (
            commands.NoPrivateMessage,
            lambda ctx, error: "This command can't be run in DMs."
        ),
        (
            commands.PrivateMessageOnly,
            lambda ctx, error: "This command can only be run in DMs."
        ),
        (
            commands.NotOwner,
            lambda ctx, error: "You need to be registered as an owner to run this command."
        ),
        (
            (commands.BadArgument, commands.BadUnionArgument),
            lambda ctx, error: str(error)
        ),
        (
            commands.TooManyArguments,
            lambda ctx, error: f"You gave too many arguments to this command - see `{ctx.clean_prefix}help {ctx.command.name}`."
        ),
        (
            discord.NotFound,
            lambda ctx, error: None
        ),
        (
            discord.Forbidden,
            lambda ctx, error: ("Discord is saying I'm unable to perform that action.", "Discord is saying I'm unable to perform that action - I probably don't have permission to talk in that channel.")
        ),
        (
            (discord.HTTPException, aiohttp.ClientOSError),
            lambda ctx, error: f"Discord messed up there somewhere - do you mind trying again? I received a {error.status} error."
        ),

        # Disabled because they're base classes for the subclasses above
        # (commands.CommandError, lambda ctx, error: ""),
        # (commands.CheckFailure, lambda ctx, error: ""),
        # (commands.CheckAnyFailure, lambda ctx, error: ""),
        # (commands.CommandInvokeError, lambda ctx, error: ""),
        # (commands.UserInputError, lambda ctx, error: ""),
        # (commands.ConversionError, lambda ctx, error: ""),
        # (commands.ArgumentParsingError, lambda ctx, error: ""),

        # Disabled because I've literally never used this and don't know anyone who has
        # (commands.MaxConcurrencyReached, lambda ctx, error: ""),

        # Disabled because they all refer to extension and command loading
        # (commands.ExtensionError, lambda ctx, error: ""),
        # (commands.ExtensionAlreadyLoaded, lambda ctx, error: ""),
        # (commands.ExtensionNotLoaded, lambda ctx, error: ""),
        # (commands.NoEntryPointError, lambda ctx, error: ""),
        # (commands.ExtensionFailed, lambda ctx, error: ""),
        # (commands.ExtensionNotFound, lambda ctx, error: ""),
        # (commands.CommandRegistrationError, lambda ctx, error: ""),
    )

    async def send_to_ctx_or_author(self, ctx:utils.Context, text:str, author_text:str=None) -> typing.Optional[discord.Message]:
        """
        Tries to send the given text to ctx, but failing that, tries to send it to the author
        instead. If it fails that too, it just stays silent.
        """

        try:
            return await ctx.send(text)
        except discord.Forbidden:
            try:
                return await ctx.author.send(author_text or text)
            except discord.Forbidden:
                pass
        except discord.NotFound:
            pass
        return None

    @utils.Cog.listener()
    async def on_command_error(self, ctx:utils.Context, error:commands.CommandError):
        """
        Global error handler for all the commands around wew.
        """

        # Set up some errors that are just straight up ignored
        ignored_errors = (
            commands.CommandNotFound, utils.errors.InvokedMetaCommand,
        )
        if isinstance(error, ignored_errors):
            return

        # See what we've got to deal with
        setattr(ctx, "original_author_id", getattr(ctx, "original_author_id", ctx.author.id))

        # Set up some errors that the owners are able to bypass
        owner_reinvoke_errors = (
            commands.MissingRole, commands.MissingAnyRole,
            commands.MissingPermissions,
            commands.CommandOnCooldown, commands.DisabledCommand,
        )
        if ctx.original_author_id in self.bot.owner_ids and isinstance(error, owner_reinvoke_errors):
            return await ctx.reinvoke()

        # See if it's in our list of common outputs
        output = None
        for error_types, function in self.COMMAND_ERROR_RESPONSES:
            if isinstance(error, error_types):
                output = function(ctx, error)
                break
        if output:
            try:
                _, _ = output
            except TypeError:
                output = (output,)
            return await self.send_to_ctx_or_author(ctx, *output)

        # Can't tell what it is? Ah well.
        try:
            await ctx.send(f'```py\n{error}```')
        except (discord.Forbidden, discord.NotFound):
            pass

        # Can't tell what it is? Let's ping the owner and the relevant webhook
        try:
            raise error
        except Exception as e:
            exc = traceback.format_exc()
            data = io.StringIO(exc)
            error_text = f"Error `{e}` encountered.\nGuild `{ctx.guild.id}`, channel `{ctx.channel.id}`, user `{ctx.author.id}`\n```\n{ctx.message.content}\n```"

            # DM to owners
            if getattr(self.bot, "config", {}).get('dm_uncaught_errors', False):
                for owner_id in self.bot.config['owners']:
                    owner = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
                    data.seek(0)
                    await owner.send(error_text, file=discord.File(data, filename="error_log.py"))

            # Ping to the webook
            if self.bot.config.get("event_webhook_url"):
                webhook = discord.Webhook.from_url(
                    self.bot.config['event_webhook_url'],
                    adapter=discord.AsyncWebhookAdapter(self.bot.session)
                )
                data.seek(0)
                await webhook.send(
                    error_text,
                    file=discord.File(data, filename="error_log.py"),
                    username=f"{self.bot.user.name} - Error"
                )

        # And throw it into the console
        raise error


def setup(bot:utils.Bot):
    x = ErrorHandler(bot)
    bot.add_cog(x)