import click

from cwmscli.commands import commands_cwms
from cwmscli.usgs import usgs_group


@click.group()
def cli():
    pass


cli.add_command(usgs_group, name="usgs")
cli.add_command(commands_cwms.shefcritimport)
cli.add_command(commands_cwms.csv2cwms_cmd)
cli.add_command(commands_cwms.blob_group)
