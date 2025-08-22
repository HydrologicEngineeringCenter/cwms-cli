import click

from cwmscli.cwms import commands_cwms
from cwmscli.getusgs import commands_getusgs


@click.group()
def cli():
    pass


cli.add_command(commands_getusgs.getUSGS_timeseries)
cli.add_command(commands_getusgs.getUSGS_ratings)
cli.add_command(commands_getusgs.ratingsinifileimport)
cli.add_command(commands_getusgs.getUSGS_measurements)
cli.add_command(commands_cwms.shefcritimport)
