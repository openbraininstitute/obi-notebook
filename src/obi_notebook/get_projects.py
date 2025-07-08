"""Example code to show complete use case."""

import ipywidgets as widgets
import requests
from entitysdk import ProjectContext
from IPython.display import display

selected_project = None  # Global variable


def project_handler(selected, project_context):
    pc = project_context["pc"]
    pc.project_id = selected["id"]
    pc.virtual_lab_id = selected["virtual_lab_id"]


def get_projects(token, project_context):
    url = "https://www.openbraininstitute.org/api/virtual-lab-manager/virtual-labs/projects"
    headers = {"authorization": f"Bearer {token}"}
    ret = requests.get(url, headers=headers)
    # Basic error handling
    if not ret.ok:
        print(f"Error fetching projects: {ret.status_code}")
        return widgets.Label("Failed to fetch projects.")

    response = ret.json()
    project_list = response.get("data", {}).get("results", [])

    if not project_list:
        return widgets.Label("No projects found.")

    options = [(project["name"], project) for project in project_list]

    project_context["pc"] = ProjectContext(
        project_id=project_list[0]["id"],
        virtual_lab_id=project_list[0]["virtual_lab_id"],
        environment="production",
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
