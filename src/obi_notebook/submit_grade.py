"""Widget for submitting an answer to the OBI grading service from a notebook."""

import json

import ipywidgets as widgets
import requests
from IPython.display import display

from obi_notebook.get_environment import get_environment


def submit_grade(env=None):
    """Display a widget that submits a per-exercise token and answer to the grading service.

    The token is the UUID handed to the learner on the LTI launch page; it is pasted into
    the widget rather than passed in code. The submit URL is derived from the deployment
    environment (production vs. staging).

    Args:
        env: Deployment environment. If ``None``, detected via ``get_environment()``.
    """
    if env is None:
        env = get_environment()

    subdomain = "cell-a" if env == "production" else "staging.cell-a"
    grade_url = f"https://{subdomain}.openbraininstitute.org/api/grading-service/grade"

    token_input = widgets.Text(
        description="Token:",
        placeholder="Paste token from the launch page",
        layout=widgets.Layout(width="700px"),
    )
    answer_input = widgets.Textarea(
        description="Answer:",
        placeholder="Type your answer (currently numeric, e.g. 42)",
        layout=widgets.Layout(width="700px", height="140px"),
    )
    submit_btn = widgets.Button(description="Submit", button_style="success", icon="check")
    status = widgets.Output()

    def on_submit(_):
        with status:
            status.clear_output()

            token = token_input.value.strip()
            raw_answer = answer_input.value.strip()

            if not token:
                print("Please paste your token from the launch page.")
                return
            if not raw_answer:
                print("Please provide an answer.")
                return

            try:
                answer = float(raw_answer)
            except ValueError:
                print("Answer must be numeric for this exercise (e.g. 42 or 42.0).")
                return

            payload = {"token": token, "answer": answer}
            submit_btn.disabled = True

            try:
                resp = requests.post(grade_url, json=payload, timeout=10)
                print(f"HTTP {resp.status_code}")

                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type.lower():
                    data = resp.json()
                    print(json.dumps(data, indent=2))
                    if resp.ok and "score" in data:
                        print(f"\nResult: {data['score'] * 100:.0f}%")
                else:
                    print(resp.text)
            except requests.RequestException as e:
                print(f"Request failed: {e}")
            finally:
                submit_btn.disabled = False

    submit_btn.on_click(on_submit)

    ui = widgets.VBox(
        [
            widgets.HTML(
                "<h3>Submit your answer</h3>"
                "<p>1) Paste token from launch page 2) Enter answer 3) Submit</p>"
            ),
            token_input,
            answer_input,
            submit_btn,
            status,
        ]
    )
    display(ui)
