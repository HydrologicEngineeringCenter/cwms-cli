from cwmscli import requirements as reqs
from cwmscli.utils.deps import requires


@requires(reqs.cwms)
def blob_group():
    pass
