"""The documentation's examples are executable, and the pages really include them.

The README used to carry three code examples that had quietly stopped working: a
renamed keyword, a renamed component, and a class that emits an ``Arm`` rather than a
guide. Prose cannot be trusted to stay true on its own, so every example on the site
is a real module here, run by this test, asserting its own claims.

Two failure modes need covering, because they look different:

* an example stops working -- caught by running it;
* a page stops *including* the example -- ``pymdownx.snippets`` fails open on an
  unknown region, rendering an empty code block in a build that still succeeds, so the
  references are checked separately.
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
EXAMPLES = DOCS / 'examples'

# Mirrors pymdownx.snippets.base_path in zensical.toml
SNIPPET_BASE_PATHS = (EXAMPLES, ROOT)

# --8<-- "file.py"  or  --8<-- "file.py:region"
SNIPPET = re.compile(r'^\s*--8<--\s+"(?P<path>[^":]+)(?::(?P<region>[\w-]+))?"', re.M)


def example_paths():
    return sorted(EXAMPLES.glob('*.py'))


@pytest.mark.parametrize('path', example_paths(), ids=lambda p: p.stem)
def test_example_runs(path, tmp_path, monkeypatch):
    """Every example executes and its own assertions hold."""
    spec = importlib.util.spec_from_file_location(f'docs_example_{path.stem}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, 'main'), f'{path.name} must define main(outdir)'
    monkeypatch.chdir(tmp_path)
    module.main(tmp_path)


def test_there_are_examples_to_run():
    """Guard against the glob silently matching nothing."""
    assert example_paths(), f'no examples found in {EXAMPLES}'


def resolve_snippet(reference: str) -> Path | None:
    for base in SNIPPET_BASE_PATHS:
        candidate = base / reference
        if candidate.is_file():
            return candidate
    return None


def snippet_references():
    for markdown in sorted(DOCS.rglob('*.md')):
        for match in SNIPPET.finditer(markdown.read_text()):
            yield markdown, match['path'], match['region']


def test_every_snippet_reference_resolves():
    """A page that includes a missing file or region renders an empty code block."""
    missing = []
    for markdown, reference, region in snippet_references():
        target = resolve_snippet(reference)
        if target is None:
            missing.append(f'{markdown.relative_to(ROOT)}: no such file {reference}')
            continue
        if region is None:
            continue
        text = target.read_text()
        if f'[start:{region}]' not in text or f'[end:{region}]' not in text:
            missing.append(
                f'{markdown.relative_to(ROOT)}: {reference} has no region {region!r}'
            )

    assert not missing, 'broken snippet references:\n  ' + '\n  '.join(missing)


def test_every_example_region_is_used():
    """An unreferenced region is a sign a page dropped its include."""
    referenced = {(resolve_snippet(r), g) for _, r, g in snippet_references()}
    unused = []
    for path in example_paths():
        for region in re.findall(r'--8<--\s+\[start:([\w-]+)\]', path.read_text()):
            if (path, region) not in referenced:
                unused.append(f'{path.name}:{region}')

    assert not unused, (
        'example regions that no page includes: ' + ', '.join(unused)
    )


def test_readme_quickstart_matches_the_tested_example():
    """GitHub cannot process snippet syntax, so the README duplicates the example.

    Asserting the duplicate is the next best thing: the README's three previous code
    blocks all rotted (a renamed keyword, a renamed reference, and a class that emits
    an Arm rather than a guide) precisely because nothing checked them.
    """
    import textwrap

    readme = (ROOT / 'README.md').read_text()
    block = re.search(r'```python\n(.*?)```', readme, re.S)
    assert block, 'the README no longer has a python example'

    example = (EXAMPLES / 'quickstart.py').read_text()
    region = example.split('# --8<-- [start:quickstart]\n')[1]
    region = region.split('    # --8<-- [end:quickstart]')[0]

    assert block.group(1).strip() == textwrap.dedent(region).strip()
