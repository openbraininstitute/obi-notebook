"""A table widget to select entities."""

import ipywidgets as widgets
import pandas as pd
import requests
from ipydatagrid import DataGrid, TextRenderer
from IPython.display import clear_output, display


def get_entities(entity_type, token, result, env="production"):
    """Select entities of type entity_type and add them to result.

    Note: The 'result' parameter is a mutable object (e.g., set) that is modified in-place
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

    # Fetch and display function
    def fetch_data(filter_values):
        params = {"page_size": 10}
        for k, v in filter_values.items():
            if k == "name":
                params["name__ilike"] = v
            else:
                params[k] = v

        headers = {"authorization": f"Bearer {token}"}

        subdomain = "www" if env == "production" else "staging"
        response = requests.get(
            f"https://{subdomain}.openbraininstitute.org/api/entitycore/{entity_type}",
            headers=headers,
            params=params,
            timeout=30,
        )

        try:
            data = response.json()
            if "data" not in data or not isinstance(data["data"], list):
                print("Unexpected API response structure:", data)
                return pd.DataFrame()
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
            grid = DataGrid(
                df,
                layout={"height": "300px"},
                auto_fit_columns=True,
                auto_fit_params={"area": "all"},
                selection_mode="row",  # Enable row selection
                selection_behavior="multi",
            )
            grid.default_renderer = TextRenderer()
            grid.auto_fit_columns = True
            display(grid)

            def on_selection_change(event, grid=grid):
                with output:
                    result.clear()
                    for selection in grid.selections:
                        for row in range(selection["r1"], selection["r2"] + 1):
                            result.add(df.iloc[row]["id"])

            grid.observe(on_selection_change, names="selections")

    for filter_ in filters_dict.values():
        filter_.observe(on_change, names="value")

    # Display
    display(widgets.HBox(list(filters_dict.values())), output)

    # Initial load
    on_change()

    return result
