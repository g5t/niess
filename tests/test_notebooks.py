"""Execute the notebooks under `docs/examples`.

A notebook is documentation that runs, which means it is documentation that can stop
running -- against a new release of anything it imports -- while looking perfectly fine on
the page. The `.py` examples next to them are executed by `test_docs_examples.py` for the
same reason; these need a kernel, so they get their own module and their own skip.

Install what they need with `pip install 'niess[examples]'`.
"""
from pathlib import Path

import pytest

nbformat = pytest.importorskip('nbformat')
nbclient = pytest.importorskip('nbclient')

EXAMPLES = Path(__file__).resolve().parent.parent / 'docs' / 'examples'
NOTEBOOKS = sorted(EXAMPLES.glob('*.ipynb'))


def requirements(notebook):
    """Third-party packages the notebook imports, so a missing one skips rather than fails.

    Only the top-level name of a plain `import x` or `from x import ...` at the start of a
    line, which is every import these notebooks make. A notebook that hides one inside a
    function is not covered, and would fail loudly, which is the right way round.
    """
    import re
    found = set()
    for cell in notebook.cells:
        if cell.cell_type != 'code':
            continue
        for line in cell.source.splitlines():
            match = re.match(r'\s*(?:import|from)\s+([A-Za-z_][\w]*)', line)
            if match:
                found.add(match.group(1))
    return {name for name in found if name not in ('niess', 'mccode_antlr')}


def test_there_are_notebooks_to_run():
    """Guard against the glob silently matching nothing."""
    assert NOTEBOOKS, f'no notebooks found under {EXAMPLES}'


@pytest.mark.parametrize('notebook', NOTEBOOKS, ids=lambda p: p.stem)
def test_every_notebook_runs(notebook, tmp_path):
    book = nbformat.read(notebook, as_version=4)
    for package in requirements(book):
        pytest.importorskip(package)

    client = nbclient.NotebookClient(
        book, timeout=1800, kernel_name='python3',
        resources={'metadata': {'path': str(notebook.parent)}},
    )
    client.execute()


@pytest.mark.parametrize('notebook', NOTEBOOKS, ids=lambda p: p.stem)
def test_no_notebook_carries_stored_output(notebook):
    """`.gitignore` excludes `*.ipynb` because stored output does not belong in a diff.

    These are tracked past that, so they have to earn it: no outputs, no execution counts,
    nothing that changes when someone opens one and runs it.
    """
    book = nbformat.read(notebook, as_version=4)
    for cell in book.cells:
        if cell.cell_type != 'code':
            continue
        assert not cell.get('outputs'), f'{notebook.name} has stored output'
        assert cell.get('execution_count') is None, f'{notebook.name} has execution counts'
