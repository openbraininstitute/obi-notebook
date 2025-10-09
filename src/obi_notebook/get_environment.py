"""Code for handling the deployment environment."""

from os import getenv

from obi_auth.typedef import DeploymentEnvironment

VAR_ENVIRONMENT = "OBI_ENVIRONMENT"


def get_environment():
    """Try to get the environment to run in from environment variable."""
    var = getenv(VAR_ENVIRONMENT)
    if var is not None:
        if var in DeploymentEnvironment._member_map_:
            return DeploymentEnvironment(var)
    return DeploymentEnvironment.production
