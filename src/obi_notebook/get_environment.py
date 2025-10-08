from os import getenv

from obi_auth.typedef import DeploymentEnvironment

VAR_ENVIRONMENT = "ENVIRONMENT"

def get_environment():
    var = getenv(VAR_ENVIRONMENT)
    if var is not None:
        if var in DeploymentEnvironment._member_map_:
            return DeploymentEnvironment(var)
    return DeploymentEnvironment.production
