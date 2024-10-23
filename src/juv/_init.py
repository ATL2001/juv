from __future__ import annotations

import sys
import tempfile
import typing
from pathlib import Path

import rich

from ._nbutils import code_cell, new_notebook, write_ipynb
from ._uv import uv


def new_notebook_with_inline_metadata(
    directory: Path,
    python: str | None = None,
) -> dict:
    """Create a new notebook with inline metadata.

    Parameters
    ----------
    directory : pathlib.Path
        A directory for uv to run `uv init` in. This is used so that we can
        defer the selection of Python (if not specified) to uv.
    python : str, optional
        A version of the Python interpreter. Provided as `--python` to uv if specified.

    Returns
    -------
    dict
        A new notebook with a single code cell containing the contents of the
        script generated by `uv init`.

    """
    with tempfile.NamedTemporaryFile(
        mode="w+",
        suffix=".py",
        delete=True,
        dir=directory,
        encoding="utf-8",
    ) as f:
        uv(
            ["init", *(["--python", python] if python else []), "--script", f.name],
            check=True,
        )
        contents = f.read().strip()
        return new_notebook(cells=[code_cell(contents, hidden=True), code_cell("")])


def get_first_non_conflicting_untitled_ipynb(directory: Path) -> Path:
    if not (directory / "Untitled.ipynb").exists():
        return directory / "Untitled.ipynb"

    for i in range(1, 100):
        if not (directory / f"Untitled{i}.ipynb").exists():
            return directory / f"Untitled{i}.ipynb"

    msg = "Could not find an available UntitledX.ipynb"
    raise ValueError(msg)


def init(
    path: Path | None,
    python: str | None,
    packages: typing.Sequence[str] = [],
) -> Path:
    """Initialize a new notebook.

    Parameters
    ----------
    path : pathlib.Path | None
        The path to the new notebook. If None, a new Untitled.ipynb is created.
    python : str | None
        The version of Python to use. Passed as `--python` to uv.
    packages : Sequence[str]
        A list of packages to install in the new notebook.

    Returns
    -------
    pathlib.Path
        The path to the new notebook.

    """
    if not path:
        path = get_first_non_conflicting_untitled_ipynb(Path.cwd())

    if path.suffix != ".ipynb":
        rich.print("File must have a `[cyan].ipynb[/cyan]` extension.", file=sys.stderr)
        sys.exit(1)

    notebook = new_notebook_with_inline_metadata(path.parent, python)
    write_ipynb(notebook, path)

    if len(packages) > 0:
        from ._add import add

        add(path=path, packages=packages, requirements=None)

    return path
