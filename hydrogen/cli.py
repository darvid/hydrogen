"""Provides the command-line entrypoint for Hydrogen."""
import functools
import sys

import click
import envoy


__all__ = (
    "main",
)


prog_name = "hydrogen"


def click_option_groups(func):
    new_func = click.option(
        "-g", "--groups",
        help="Comma-separated list of requirement groups to include.",
    )(func)
    return functools.update_wrapper(new_func, func)


@click.group()
@click.version_option(prog_name=prog_name)
@click.pass_context
def main(ctx):
    """Micro-manage package managers."""
    which = "where" if sys.platform == "win32" else "which"
    if envoy.run(which + " git").status_code != 0:
        click.secho("fatal: git not found in PATH", fg="red")
        sys.exit(1)
    # ctx.obj = Hydrogen()
