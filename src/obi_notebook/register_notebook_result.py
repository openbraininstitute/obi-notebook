"""Register .ipynb files as AnalysisNotebookResult."""

from datetime import datetime
from glob import glob
from os import path
from pathlib import Path
from typing import cast

import ipywidgets as widgets
from entitysdk import Client, EntitySDKError, models, types
from entitysdk.types import ID
from IPython.display import clear_output, display
from obi_auth import get_user_info


def _find_potential_notebook_files() -> list[str]:
    """Find .ipynb files in the the current working directory."""
    return list(glob("*.ipynb"))


def _file_last_saved_str(fn: str) -> str:
    """For a file path, create a string that describes when it was last saved."""
    modified = datetime.fromtimestamp(Path(fn).stat().st_mtime)
    delta = datetime.now() - modified

    seconds = int(delta.total_seconds())

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days:
        parts.append(f"{days} day(s)")
    if hours:
        parts.append(f"{hours} hour(s)")
    if minutes:
        parts.append(f"{minutes} minute(s)")

    parts.append(f"{seconds} second(s) ago")

    return "Last saved: " + " ".join(parts)


def _this_user(client: Client) -> str | None:
    """Get the authenticated user's "sub_id" for use with queries."""
    user_info = get_user_info(client._token_manager.get_token())
    return user_info["sub"]


def _try_to_find_matching_entity(client: Client, notebook_name: str, user_sub: str | None = None):
    """For a 'name' string and user sub_id return matching NotebookResult entities."""
    if user_sub is None:
        query = {"name": notebook_name, "authorized_public": False}
    else:
        query = {"created_by__sub_id": user_sub, "name": notebook_name, "authorized_public": False}
    query_res = client.search_entity(entity_type=models.AnalysisNotebookResult, query=query)
    return query_res.all()


def _entity_str(entity: models.AnalysisNotebookResult) -> str:
    """For a NotebookResult entity, create a descriptive string."""
    update_date = cast(datetime, entity.update_date)
    return f"{entity.name}: {update_date.strftime('%Y-%m-%d %H:%M')}"


def _nb_entity_description(client: Client, entity_id: ID) -> str:
    """For a NotebookResult entity, return its .description property as a str."""
    entity = client.get_entity(entity_id=entity_id, entity_type=models.AnalysisNotebookResult)
    return str(entity.description)


def _register_result(
    client: Client, notebook_file: Path, notebook_name: str, notebook_description: str
) -> tuple[ID, ID]:
    """Create and register a new NotebookResult entity."""
    print("Creating notebook entity...")
    nb_entity_raw = models.AnalysisNotebookResult(
        name=notebook_name, description=notebook_description, authorized_public=False
    )
    print("Registerig notebook entity...")
    nb_entity_register = client.register_entity(entity=nb_entity_raw)
    if nb_entity_register.id is not None:
        print("...success! Uploading notebook file...")
        asset_obj = client.upload_file(
            entity_id=nb_entity_register.id,
            entity_type=models.AnalysisNotebookResult,
            file_path=notebook_file,
            file_name=path.split(notebook_file)[1],
            file_content_type=types.ContentType.application_x_ipynb_json,
            asset_label=types.AssetLabel.jupyter_notebook,
        )
        asset_id = cast(ID, asset_obj.id)
        print("...NotebookResult successfully created!")
        return nb_entity_register.id, asset_id

    print("...registration failed!")
    raise EntitySDKError()


def _update_result(
    client: Client,
    entity_id: ID,
    notebook_file: Path,
    notebook_name: str,
    notebook_description: str,
):
    """Update an existing NotebookResult entity (name, description and assets)."""
    nb_entity_found = client.get_entity(
        entity_id=entity_id, entity_type=models.AnalysisNotebookResult
    )

    print("Updating notebook entity...")
    if (notebook_name != nb_entity_found.name) or (
        notebook_description != nb_entity_found.description
    ):
        print("Updating name and description...")
        client.update_entity(
            entity_id=entity_id,
            entity_type=models.AnalysisNotebookResult,
            attrs_or_entity={"name": notebook_name, "description": notebook_description},
        )
    assets = client.select_assets(
        entity=nb_entity_found, selection={"label": types.AssetLabel.jupyter_notebook}
    ).all()
    for asset in assets:
        print("Deleting existing asset...")
        client.delete_asset(
            entity_id=entity_id,
            entity_type=models.AnalysisNotebookResult,
            asset_id=asset.id,
        )
    print("Uploding new asset...")
    asset_obj = client.upload_file(
        entity_id=entity_id,
        entity_type=models.AnalysisNotebookResult,
        file_path=notebook_file,
        file_name=notebook_file.name,
        file_content_type=types.ContentType.application_x_ipynb_json,
        asset_label=types.AssetLabel.jupyter_notebook,
    )
    print("...NotebookResult successfully updated!")
    return nb_entity_found.id, asset_obj.id


class NotebookResultRegistration:
    """Helper class for the registration of notebooks."""

    def __init__(self):
        """Initialize registration helper."""
        self._notebook_file = None
        self._notebook_name = None
        self._notebook_description = None
        self._notebook_entity_id = None
        self._user = None

    def register(self, client: Client) -> None:
        """Display widgets for the registration of a notebook."""
        list_of_notebook_options = _find_potential_notebook_files()
        if len(list_of_notebook_options) == 0:
            raise ValueError("Could not find notebook file to register!")

        if self._user is None:
            self._user = _this_user(client)

        # Dropdown with your options
        value = self._notebook_file or list_of_notebook_options[0]
        dropdown = widgets.Dropdown(
            options=list_of_notebook_options,
            description="Choose notebook file to register:",
            style={"description_width": "initial"},
            value=value,
        )
        display_last_save = widgets.Label(_file_last_saved_str(value))

        # Text box for notebook result entity name
        name_box = widgets.Text(
            placeholder="Enter a name",
            description="Name:",
            value=self._notebook_name,
            style={"description_width": "initial"},
        )

        # Text area for notebook result entity description
        desc_box = widgets.Textarea(
            placeholder="Enter a description",
            description="Description:",
            value=self._notebook_description,
            layout=widgets.Layout(width="400px", height="80px"),
            style={"description_width": "initial"},
        )

        # Confirm button
        confirm_btn = widgets.Button(description="Register", button_style="success")

        lst_found_entites = []
        if self._notebook_entity_id is not None and self._notebook_name is not None:
            self_entity = client.get_entity(
                self._notebook_entity_id, entity_type=models.AnalysisNotebookResult
            )
            lst_found_entites.append((_entity_str(self_entity), self._notebook_entity_id))
            lst_found_entites.append(("New result", None))
            confirm_btn = widgets.Button(description="Update", button_style="info")
        else:
            lst_found_entites.append(("New result", None))
            confirm_btn = widgets.Button(description="Register", button_style="success")
        sel_existing = widgets.Dropdown(
            description="Overwrite or create new",
            options=lst_found_entites,
            style={"description_width": "initial"},
        )

        lst_widgets = [dropdown, display_last_save, name_box, sel_existing, desc_box, confirm_btn]

        # --------------------------------------------------------------
        #   Assemble the UI
        # --------------------------------------------------------------
        ui = widgets.VBox(lst_widgets)
        out = widgets.Output()  # optional – for post‑confirmation messages
        display(ui, out)

        # --------------------------------------------------------------
        #   Callbacks that update other widgets
        # --------------------------------------------------------------
        # "Name" text box -> Update dropdown options unless there was a previous save.
        def _on_name_changed(change):
            if self._notebook_entity_id is None:
                lst_found = _try_to_find_matching_entity(client, change["new"].strip(), self._user)
                options_found = [("New result", None)] + [
                    (_entity_str(found), found.id) for found in lst_found
                ]
                sel_existing.options = options_found
                sel_existing.index = 0

        # Dropdown selection -> Update button: register or update. Also description str.
        def _on_selection_change(change):
            if change["new"] is None:
                confirm_btn.description = "Register"
                confirm_btn.button_style = "success"
            else:
                confirm_btn.description = "Update"
                confirm_btn.button_style = "info"
                desc_box.value = _nb_entity_description(client, change["new"])

        def _on_file_selection_change(change):
            display_last_save.value = _file_last_saved_str(change["new"])

        dropdown.observe(_on_file_selection_change, names="value")
        name_box.observe(_on_name_changed, names="value")
        sel_existing.observe(_on_selection_change, names="value")

        # --------------------------------------------------------------
        #   Callback that runs registration
        # --------------------------------------------------------------
        def _on_confirm_clicked(b):
            # Grab the entered values
            self._notebook_file = dropdown.value
            self._notebook_name = name_box.value.strip()
            self._notebook_description = desc_box.value.strip()

            # Give the user quick feedback
            chosen_file_path = Path(self._notebook_file)
            if not chosen_file_path.exists():
                err_str = f"{self._notebook_file} does not exist!"
                raise ValueError(err_str)

            with out:
                clear_output()
                try:
                    if sel_existing.value is not None:
                        entity_id, _ = _update_result(
                            client,
                            entity_id=sel_existing.value,
                            notebook_file=chosen_file_path,
                            notebook_name=self._notebook_name,
                            notebook_description=self._notebook_description,
                        )
                    else:
                        entity_id, _ = _register_result(
                            client,
                            notebook_file=chosen_file_path,
                            notebook_name=self._notebook_name,
                            notebook_description=self._notebook_description,
                        )
                    self._notebook_entity_id = entity_id
                except EntitySDKError as err:
                    if "401" in err.args[0]:
                        print("""Not authenticated or authentication expired.
                        Please re-run the platform authentication at the top of the notebook!""")
                    elif "403" in err.args[0]:
                        print("""No sufficient rights to create or update NotebookResult.
                        Please create a new entity instead of overwriting an existing!""")

            # Close the UI so the notebook stays tidy
            ui.close()

        # Register the click handler
        confirm_btn.on_click(_on_confirm_clicked)


register_result = NotebookResultRegistration()
