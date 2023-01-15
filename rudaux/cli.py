import click
from fwirl.api import (
    summarize as api_summarize,
)
from fwirl.message import __RABBIT_URL__
from manager import run


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
@click.option("--config_path", default="../rudaux_config.yml")
def run(config_path):
    run(config_path)


cli.add_command(run)

