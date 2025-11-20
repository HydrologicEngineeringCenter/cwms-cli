import click


def to_uppercase(ctx, param, value):
    if value is None:
        return None
    return value.upper()


office_option = click.option(
    "-o",
    "--office",
    required=True,
    envvar="OFFICE",
    type=str,
    callback=to_uppercase,
    help="Office to grab data for",
)
api_root_option = click.option(
    "-a",
    "--api_root",
    required=True,
    envvar="CDA_API_ROOT",
    type=str,
    help="Api Root for CDA. Can be user defined or placed in a env variable CDA_API_ROOT",
)
api_coop_root_option = click.option(
    "--coop",
    is_flag=True,
    envvar="CDA_API_COOP_ROOT",
    type=str,
    help="Use CDA_API_COOP_ROOT from env",
)

api_key_option = click.option(
    "-k",
    "--api_key",
    default=None,
    type=str,
    envvar="CDA_API_KEY",
    help="api key for CDA. Can be user defined or place in env variable CDA_API_KEY. one of api_key or api_key_loc are required",
)
api_key_loc_option = click.option(
    "-kl",
    "--api_key_loc",
    default=None,
    type=str,
    help="file storing Api Key. One of api_key or api_key_loc are required",
)


def get_api_key(api_key: str, api_key_loc: str) -> str:
    if api_key is not None:
        return api_key
    elif api_key_loc is not None:
        with open(api_key_loc, "r") as f:
            return f.readline().strip()
    else:
        raise Exception(
            "must add a value to either --api_key(-k) or --api_key_loc(-kl)"
        )


def common_api_options(f):
    f = office_option(f)
    f = api_root_option(f)
    f = api_key_option(f)
    return f
