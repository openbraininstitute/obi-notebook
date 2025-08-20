import obi_auth
from obi_notebook import get_projects

token = obi_auth.get_token(environment="production", auth_mode="daf")
project_context = get_projects.get_projects(token)
