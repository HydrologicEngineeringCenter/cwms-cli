import click
from cwmscli.getusgs import __getusgs_commands

@click.group()
def cli():
    pass


cli.add_command(__getusgs_commands.getusgs_timeseries)
cli.add_command(__getusgs_commands.getusgs_ratings)
cli.add_command(__getusgs_commands.getusgs_ratings_INIFileImport)
cli.add_command(__getusgs_commands.getusgs_measurements)


