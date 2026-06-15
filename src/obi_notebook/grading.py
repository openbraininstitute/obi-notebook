"""Notebook-side helper for the OBI grading service.

The Notebook Service writes a ``.grading.json`` launch file into the student's
pod next to the notebook. This module reads that file, fetches the per-student
exercise parameters from the grading service, and submits answers back to it.

Typical notebook usage::

    from obi_notebook import grading

    exercise = grading.load()  # reads .grading.json, fetches params
    a, b = exercise.params["a"], exercise.params["b"]
    exercise.submit(my_solution(a, b))  # cell renders "You scored 100%"

See the grading-service ``docs/system-design.md`` for the full launch-and-grading
contract. The grading-service base URL is resolved at runtime from
``OBI_ENVIRONMENT`` and is never read from the launch file.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, cast

import requests

from obi_notebook.get_environment import get_environment

LAUNCH_FILENAME = ".grading.json"
_TIMEOUT = 30


class GradingError(Exception):
    """Raised when the grading service rejects a request (e.g. expired token)."""


def _base_url(env: object) -> str:
    """Return the grading-service base URL for a deployment environment."""
    subdomain = "cell-a" if env == "production" else "staging.cell-a"
    return f"https://{subdomain}.openbraininstitute.org/api/grading-service"


def _detail(resp: requests.Response, fallback: str) -> str:
    """Extract a human-readable detail message from an error response."""
    try:
        payload = resp.json()
    except ValueError:
        return resp.text or fallback
    if isinstance(payload, dict):
        data = cast("dict[str, Any]", payload)
        detail = data.get("detail") or data.get("message")
        if detail:
            return str(detail)
    return fallback


def _user_ns_get(key: str) -> Any:
    """Read a name from the interactive IPython namespace, if running under one.

    The notebook-path globals (``__session__``, ``__vsc_ipynb_file__``) live in
    the user's interactive namespace, not in this module's globals.
    """
    try:
        from IPython.core.getipython import get_ipython
    except Exception:  # noqa: BLE001 - IPython may be absent or misbehaving
        return None
    shell = get_ipython()
    if shell is None:
        return None
    namespace = cast("dict[str, Any]", getattr(shell, "user_ns", {}))
    return namespace.get(key)


def _notebook_dir() -> Path:
    """Best-effort resolution of the directory containing the running notebook.

    The kernel CWD is not a reliable proxy for the notebook's location (spawners
    may launch from a fixed root, and ``os.chdir`` moves it), so prefer the
    notebook path published by the Jupyter server, falling back to CWD.
    """
    # 1. JPY_SESSION_NAME: absolute .ipynb path (Jupyter Server >= 2 / ipykernel >= 6.21).
    # 2/3. user-namespace globals set by the interactive shell (JupyterLab / VS Code).
    hint = (
        os.environ.get("JPY_SESSION_NAME")
        or _user_ns_get("__session__")
        or _user_ns_get("__vsc_ipynb_file__")
    )
    if hint:
        parent = Path(hint).resolve().parent
        if parent.is_dir():
            return parent
    return Path.cwd()


def _find_launch_file(start: str | Path | None = None) -> Path | None:
    """Search for ``.grading.json`` from ``start`` upward through parent dirs."""
    base = Path(start).resolve() if start else _notebook_dir().resolve()
    for directory in [base, *base.parents]:
        candidate = directory / LAUNCH_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _fetch_params(base: str, token: str) -> dict[str, Any]:
    """Fetch the per-student params bound to ``token`` from ``GET /params``."""
    try:
        resp = requests.get(
            f"{base}/params",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GradingError(f"Could not reach the grading service at {base}: {exc}") from exc
    if resp.status_code == 404:
        raise GradingError(
            f"Grading service returned 404 for GET {base}/params. The grading-service "
            "route is likely misconfigured or unreachable. "
            "The notebook cannot fetch exercise parameters until this is resolved."
        )
    if resp.status_code in (401, 403):
        raise GradingError(_detail(resp, "Grading service rejected the launch token."))
    if not resp.ok:
        raise GradingError(_detail(resp, f"Grading service returned HTTP {resp.status_code}."))
    try:
        body = resp.json()
    except ValueError:
        return {}
    if isinstance(body, dict):
        params = cast("dict[str, Any]", body).get("params", {})
        if isinstance(params, dict):
            return cast("dict[str, Any]", params)
    return {}


class GradeResult:
    """Outcome of an :meth:`Exercise.submit` call.

    Carries the numeric ``score`` and the server ``message`` for programmatic use,
    and renders a styled summary when displayed as the value of a notebook cell.

    Attributes:
        ok: Whether the grade request succeeded (HTTP 2xx).
        status_code: The HTTP status returned by ``POST /grade``.
        score: The numeric score (``0.0``-``1.0``), or ``None`` on error.
        message: The human-readable message from the grading service.
        exercise_id: The exercise the answer was graded against.
        raw: The parsed JSON body (or raw text when not JSON).
    """

    def __init__(
        self,
        *,
        ok: bool,
        status_code: int,
        score: float | None,
        message: str,
        exercise_id: str | None,
        raw: Any,
    ) -> None:
        """Store the fields of a graded answer; see class docstring."""
        self.ok = ok
        self.status_code = status_code
        self.score = score
        self.message = message
        self.exercise_id = exercise_id
        self.raw = raw

    @classmethod
    def from_transport_error(cls, exc: Exception, *, exercise_id: str | None) -> GradeResult:
        """Build a :class:`GradeResult` for a request that never received a response.

        Used when ``POST /grade`` fails at the transport layer (connection error,
        timeout) so the student gets a styled, retryable result rather than a raw
        traceback. ``status_code`` is ``0`` to signal "no HTTP response".
        """
        return cls(
            ok=False,
            status_code=0,
            score=None,
            message=f"Could not reach the grading service: {exc}",
            exercise_id=exercise_id,
            raw=None,
        )

    @classmethod
    def from_response(cls, resp: requests.Response) -> GradeResult:
        """Build a :class:`GradeResult` from a ``POST /grade`` HTTP response."""
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        data: dict[str, Any] = cast("dict[str, Any]", payload) if isinstance(payload, dict) else {}
        # Only fall back to the raw body on errors; on success leave message empty
        # so _headline can derive "You scored X%" from the score.
        message = data.get("message") or data.get("detail") or ""
        if not message and not resp.ok:
            message = resp.text
        return cls(
            ok=resp.ok,
            status_code=resp.status_code,
            score=data.get("score"),
            message=str(message),
            exercise_id=data.get("exercise_id"),
            raw=data or resp.text,
        )

    def _headline(self) -> str:
        """Return the leading message, derived from the score if none was sent."""
        if self.message:
            return str(self.message)
        if self.ok and isinstance(self.score, (int, float)):
            return f"You scored {self.score * 100:.0f}%"
        return f"Grading failed (HTTP {self.status_code})."

    def __repr__(self) -> str:
        """Return a concise text representation for non-notebook contexts."""
        return (
            f"GradeResult(ok={self.ok}, status_code={self.status_code}, "
            f"score={self.score!r}, message={self._headline()!r})"
        )

    def _repr_html_(self) -> str:
        """Render a styled result box for display in a notebook cell."""
        if self.ok:
            color, background, icon = "#1a7f37", "#e9f7ec", "✓"
        elif self.status_code == 400:
            color, background, icon = "#9a6700", "#fff8e1", "✎"
        else:
            color, background, icon = "#b42318", "#fdecea", "✗"
        headline = html.escape(self._headline())
        return (
            f'<div style="border-left:4px solid {color};background:{background};'
            "padding:10px 14px;border-radius:4px;font-family:sans-serif;"
            f'color:{color};font-size:1.1em;">{icon} {headline}</div>'
        )


class Exercise:
    """A launched exercise: its per-student params and a way to submit answers.

    Returned by :func:`load`. ``params`` is the seeded parameter dict for this
    student (``{}`` when the exercise opts out of per-student parameterization).
    """

    def __init__(
        self,
        *,
        token: str,
        exercise_id: str,
        params: dict[str, Any],
        base: str,
    ) -> None:
        """Store the launch context; see :func:`load` for how it is populated."""
        self._token = token
        self.exercise_id = exercise_id
        self.params = params
        self._base = base

    def submit(self, answer: Any) -> GradeResult:
        """Submit ``answer`` to ``POST /grade`` and return a :class:`GradeResult`.

        Args:
            answer: Any JSON-serializable answer value for this exercise.

        Returns:
            A :class:`GradeResult`; an error response (e.g. a shape-rejected
            answer) or a transport failure (connection error / timeout) is
            returned as a result, not raised, so the student can retry.
        """
        payload: dict[str, Any] = {
            "token": self._token,
            "answer": answer,
            "exercise_id": self.exercise_id,
        }
        try:
            resp = requests.post(f"{self._base}/grade", json=payload, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            return GradeResult.from_transport_error(exc, exercise_id=self.exercise_id)
        return GradeResult.from_response(resp)

    def __repr__(self) -> str:
        """Return a concise text representation of the exercise handle."""
        return f"Exercise(exercise_id={self.exercise_id!r}, params={self.params!r})"


def load(
    token: str | None = None,
    exercise_id: str | None = None,
    env: str | None = None,
    path: str | Path | None = None,
) -> Exercise:
    """Load the launched exercise and eagerly fetch its per-student parameters.

    Finds the ``.grading.json`` launch file next to the notebook (walking up
    parent directories), resolves the grading-service base URL from the
    deployment environment, and fetches ``GET /params`` so ``exercise.params`` is
    ready on return.

    Args:
        token: Launch token. If both ``token`` and ``exercise_id`` are given, the
            launch file is not read (useful for local testing outside a pod).
        exercise_id: Exercise key. See ``token``.
        env: Deployment environment. If ``None``, detected via ``get_environment``.
        path: Explicit path to a ``.grading.json`` file, bypassing discovery.

    Returns:
        An :class:`Exercise` handle.

    Raises:
        FileNotFoundError: No launch file was found and no overrides were passed.
        ValueError: The launch file is missing ``token`` or ``exercise_id``.
        GradingError: The grading service rejected the token, or could not serve params.
    """
    resolved_env: object = env if env is not None else get_environment()
    base = _base_url(resolved_env)

    if token is None or exercise_id is None:
        launch_path = Path(path) if path else _find_launch_file()
        if launch_path is None or not launch_path.is_file():
            raise FileNotFoundError(
                f"No {LAUNCH_FILENAME} launch file found near the notebook. This notebook "
                "must be opened from a grading launch, or pass token=... and exercise_id=... "
                "explicitly for local testing."
            )
        data = cast("dict[str, Any]", json.loads(launch_path.read_text()))
        token = token or data.get("token")
        exercise_id = exercise_id or data.get("exercise_id")
        if not token or not exercise_id:
            raise ValueError(f"{launch_path} is missing 'token' or 'exercise_id'.")

    params = _fetch_params(base, token)
    return Exercise(token=token, exercise_id=exercise_id, params=params, base=base)
