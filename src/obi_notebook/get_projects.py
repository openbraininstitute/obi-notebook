"""Example code to show complete use case."""

import ipywidgets as widgets
import requests

from os import getenv
from entitysdk import ProjectContext
from IPython.display import display

from obi_notebook.get_environment import get_environment

selected_project = None  # Global variable

VAR_PROJECT = "OBI_PROJECT_ID"

def get_default_project(project_list):
    """Try to guess the project id to use from a list using:
      1. a globally defined variable, or
      2. an environment variable.
      Fallback is simply the first project in the list."""
    glbl_proj_str = None
    try:
        from __main__ import OBI_PROJECT_ID
        glbl_proj_str = OBI_PROJECT_ID
    except ImportError:
        pass
    for i, proj in enumerate(project_list):
        if proj["id"] == glbl_proj_str:
            return i
    var = getenv(VAR_PROJECT)
    for i, proj in enumerate(project_list):
        if proj["id"] == var:
            return i
    return 0

def get_projects(token, env=None):
    """Returns available project for the end user."""
    if env is None:
        env = get_environment()

    def project_handler(selected, project_context):
        project_context.project_id = selected["id"]
        project_context.virtual_lab_id = selected["virtual_lab_id"]

    subdomain = "www" if env == "production" else "staging"

    url = (
        f"https://{subdomain}.openbraininstitute.org/api/virtual-lab-manager/virtual-labs/projects"
    )
    headers = {"authorization": f"Bearer {token}"}
    ret = requests.get(url, headers=headers, timeout=30)
    # Basic error handling
    if not ret.ok:
        print(f"Error fetching projects: {ret.status_code}")
        return widgets.Label("Failed to fetch projects.")

    response = ret.json()
    project_list = response.get("data", {}).get("results", [])

    if not project_list:
        return widgets.Label("No projects found.")

    options = [(project["name"], project) for project in project_list]
    default_sel_idx = get_default_project(project_list)

    project_context = ProjectContext(
        project_id=project_list[default_sel_idx]["id"],
        virtual_lab_id=project_list[default_sel_idx]["virtual_lab_id"],
        environment=env,
    )
    dropdown = widgets.Dropdown(
        options=options,
        description="Select:",
        index=default_sel_idx,
    )

    def on_change(change):
        if change["type"] == "change" and change["name"] == "value":
            global selected_project
            selected_project = change["new"]
            project_handler(selected_project, project_context)

    dropdown.observe(on_change)
    display(dropdown)
    return project_context
