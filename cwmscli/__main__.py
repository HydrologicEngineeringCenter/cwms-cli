import click

from cwmscli.commands import commands_cwms
from cwmscli.getusgs import commands_getusgs


@click.group()
def cli():
    pass


cli.add_command(commands_getusgs.getusgs_timeseries)
cli.add_command(commands_getusgs.getusgs_ratings)
cli.add_command(commands_getusgs.ratingsinifileimport)
cli.add_command(commands_getusgs.getusgs_measurements)
cli.add_command(commands_cwms.shefcritimport)
cli.add_command(commands_cwms.csv2cwms_cmd)
