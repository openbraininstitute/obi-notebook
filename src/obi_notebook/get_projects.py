"""Example code to show complete use case."""

import ipywidgets as widgets
import requests
from entitysdk import ProjectContext
from IPython.display import display

selected_project = None  # Global variable


def get_projects(token, env="production"):
    """Returns available project for the end user."""

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

    project_context = ProjectContext(
        project_id=project_list[0]["id"],
        virtual_lab_id=project_list[0]["virtual_lab_id"],
        environment=env,
    )
    dropdown = widgets.Dropdown(
        options=options,
        description="Select:",
    )

    def on_change(change):
        if change["type"] == "change" and change["name"] == "value":
            global selected_project
            selected_project = change["new"]
            project_handler(selected_project, project_context)

    dropdown.observe(on_change)
    display(dropdown)
    return project_context
