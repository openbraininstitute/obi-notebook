"""A table widget to select entities."""

import ipywidgets as widgets
import pandas as pd
import requests
from entitysdk import Client, models
from ipydatagrid import DataGrid, TextRenderer
from IPython.display import clear_output, display


def _estimate_column_widths(df, char_width=8, padding=2, max_size=250):
    widths = {}
    for col in df.columns:
        max_len = max(df[col].astype(str).map(len).max(), len(col))
        widths[col] = min(max_size, max_len * char_width + padding)
    return widths


def get_entities(
    entity_type, token, result, env="production", project_context=None, return_entities=False
):
    """Select entities of type entity_type and add them to result.

    Note: The 'result' parameter is a mutable object (a list) that is modified in-place
      and also returned.
    """
    # Widgets
    filters_dict = {}
    if entity_type == "circuit":
        scale_filter = widgets.Dropdown(
            options=["single", "pair", "small", "microcircuit", "region", "system", "whole"],
            description="Scale:",
        )
        filters_dict["scale"] = scale_filter

    filters_dict["name"] = widgets.Text(description="Name:")

    # Output area
    output = widgets.Output()

    subdomain = "www" if env == "production" else "staging"
    entity_core_url = f"https://{subdomain}.openbraininstitute.org/api/entitycore"

    # Fetch and display function
    def fetch_data(filter_values):
        params = {"page_size": 10}
        for k, v in filter_values.items():
            if k == "name":
                params["name__ilike"] = v
            else:
                params[k] = v

        headers = {"authorization": f"Bearer {token}"}
        if project_context:
            headers["virtual-lab-id"] = project_context.virtual_lab_id
            headers["project-id"] = project_context.project_id
        response = requests.get(
            f"{entity_core_url}/{entity_type}",
            headers=headers,
            params=params,
            timeout=30,
        )

        try:
            data = response.json()
            df = pd.json_normalize(data["data"])
            return df
        except Exception as e:
            print("Error fetching or parsing data:", e)
            return pd.DataFrame()

    grid = None

    # On change callback
    def on_change(change=None):
        nonlocal result
        nonlocal grid
        with output:
            clear_output()
            filter_values = {k: v.value for k, v in filters_dict.items()}
            df = fetch_data(filter_values)

            proper_columns = [
                "id",
                "name",
                "description",
                "brain_region.name",
                "subject.species.name",
            ]
            if len(df) == 0:
                print("no results")
                return

            df = df[proper_columns].reset_index(drop=True)
            column_widths = _estimate_column_widths(df)
            grid = DataGrid(
                df,
                layout={"height": "300px"},
                # auto_fit_columns=True,
                auto_fit_params={"area": "all"},
                selection_mode="row",  # Enable row selection
                selection_behavior="multi",
                column_widths=column_widths,
            )
            grid.default_renderer = TextRenderer()
            display(grid)

            def on_selection_change(event, grid=grid):
                with output:
                    result.clear()
                    l_ids = set()
                    for selection in grid.selections:
                        for row in range(selection["r1"], selection["r2"] + 1):
                            l_ids.add(df.iloc[row]["id"])

                    if return_entities:
                        client = Client(
                            api_url=entity_core_url,
                            project_context=project_context,
                            token_manager=token,
                        )

                        model_class = getattr(models, entity_type.capitalize())
                        retrieved_entities = client.search_entity(
                            entity_type=model_class, query={"id__in": list(l_ids)}
                        )
                        result.extend(retrieved_entities)
                    else:
                        result.extend(l_ids)

            grid.observe(on_selection_change, names="selections")

    for filter_ in filters_dict.values():
        filter_.observe(on_change, names="value")

    # Display
    display(widgets.HBox(list(filters_dict.values())), output)

    # Initial load
    on_change()

    return result
