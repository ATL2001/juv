from __future__ import annotations

import tempfile
import typing
from pathlib import Path

import jupytext
from jupytext.pandoc import subprocess
from uv import find_uv_bin

from ._nbutils import code_cell, write_ipynb
from ._pep723 import includes_inline_metadata
from ._uv import uv

T = typing.TypeVar("T")


def find(cb: typing.Callable[[T], bool], items: list[T]) -> T | None:
    """Find the first item in a list that satisfies a condition.

    Parameters
    ----------
    cb : Callable[[T], bool]
        The condition to satisfy.
    items : list[T]
        The list to search.

    Returns
    -------
    T | None
        The first item that satisfies the condition, or None if no item does.

    """
    return next((item for item in items if cb(item)), None)


def uv_pip_compile(
    packages: typing.Sequence[str],
    requirements: str | None,
    *,
    no_deps: bool,
    exclude_newer: str | None,
) -> list[str]:
    """Use `pip compile` to generate exact versions of packages."""
    requirements_txt = "" if requirements is None else Path(requirements).read_text()

    # just append the packages on to the requirements
    for package in packages:
        if package not in requirements_txt:
            requirements_txt += f"{package}\n"

    result = subprocess.run(
        [
            find_uv_bin(),
            "pip",
            "compile",
            *(["--no-deps"] if no_deps else []),
            *([f"--exclude-newer={exclude_newer}"] if exclude_newer else []),
            "-",
        ],
        input=requirements_txt.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode())

    # filter only for the exact versions
    return [pkg for pkg in result.stdout.decode().split("\n") if "==" in pkg]


def uv_script(  # noqa: PLR0913
    script: Path | str,
    *,
    packages: typing.Sequence[str],
    requirements: str | None,
    extras: typing.Sequence[str] | None,
    editable: bool,
    branch: str | None,
    rev: str | None,
    tag: str | None,
    exclude_newer: str | None,
) -> None:
    uv(
        [
            "add",
            *(["--requirements", requirements] if requirements else []),
            *([f"--extra={extra}" for extra in extras or []]),
            *(["--editable"] if editable else []),
            *([f"--tag={tag}"] if tag else []),
            *([f"--branch={branch}"] if branch else []),
            *([f"--rev={rev}"] if rev else []),
            *([f"--exclude-newer={exclude_newer}"] if exclude_newer else []),
            "--script",
            str(script),
            *packages,
        ],
        check=True,
    )


def add_notebook(  # noqa: PLR0913
    path: Path,
    *,
    packages: typing.Sequence[str],
    requirements: str | None,
    extras: typing.Sequence[str] | None,
    editable: bool,
    branch: str | None,
    rev: str | None,
    tag: str | None,
    exclude_newer: str | None,
) -> None:
    notebook = jupytext.read(path, fmt="ipynb")

    # need a reference so we can modify the cell["source"]
    cell = find(
        lambda cell: (
            cell["cell_type"] == "code"
            and includes_inline_metadata("".join(cell["source"]))
        ),
        notebook["cells"],
    )

    if cell is None:
        notebook["cells"].insert(0, code_cell("", hidden=True))
        cell = notebook["cells"][0]

    with tempfile.NamedTemporaryFile(
        mode="w+",
        delete=True,
        suffix=".py",
        dir=path.parent,
        encoding="utf-8",
    ) as f:
        f.write(cell["source"].strip())
        f.flush()
        uv_script(
            script=f.name,
            packages=packages,
            requirements=requirements,
            extras=extras,
            editable=editable,
            branch=branch,
            rev=rev,
            tag=tag,
            exclude_newer=exclude_newer,
        )
        f.seek(0)
        cell["source"] = f.read().strip()

    write_ipynb(notebook, path.with_suffix(".ipynb"))


def add(  # noqa: PLR0913
    *,
    path: Path,
    packages: typing.Sequence[str],
    requirements: str | None = None,
    extras: typing.Sequence[str] | None = None,
    tag: str | None = None,
    branch: str | None = None,
    rev: str | None = None,
    pin: bool = False,
    editable: bool = False,
    exclude_newer: str | None = None,
) -> None:
    if pin:
        packages = uv_pip_compile(
            packages, requirements, exclude_newer=exclude_newer, no_deps=True
        )
        requirements = None

    (add_notebook if path.suffix == ".ipynb" else uv_script)(
        path,
        packages=packages,
        requirements=requirements,
        extras=extras,
        editable=editable,
        branch=branch,
        rev=rev,
        tag=tag,
        exclude_newer=exclude_newer,
    )
