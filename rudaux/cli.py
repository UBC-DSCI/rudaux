import click
from fwirl.api import (
    summarize as api_summarize,
    ls as api_ls,
    refresh as api_refresh,
    build as api_build,
    pause as api_pause,
    unpause as api_unpause,
    schedule as api_schedule,
    unschedule as api_unschedule,
    shutdown as api_shutdown
)
from fwirl.message import __RABBIT_URL__


@click.group()
def cli():
    pass


@click.command()
@click.argument("graph")
@click.option("--rabbit_url", default=__RABBIT_URL__)
def summarize(graph, rabbit_url):
    api_summarize(graph, rabbit_url)


cli.add_command(summarize)


@click.command()
@click.argument("graph")
@click.option("--rabbit_url", default=__RABBIT_URL__)
def shutdown(graph, rabbit_url):
    api_shutdown(graph, rabbit_url)


cli.add_command(shutdown)


# run: calls the run from graph and build the grraph and call initialize and run
# arg: path to the configfile

# summarize: uses fwirl api
