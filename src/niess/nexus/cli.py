"""Command-line conversion of an instrument to NeXus Structure JSON.

Replaces ``moreniius``'s ``instr2ns`` entry point.
"""
from __future__ import annotations

from pathlib import Path


def load_instr(filepath: str | Path):
    """Load an ``Instr`` from a McCode ``.instr`` file or a serialized instrument."""
    filepath = Path(filepath)
    if not filepath.is_file():
        raise ValueError(f'{filepath} does not exist or is not a file')

    suffix = filepath.suffix.lower()
    if suffix == '.instr':
        from mccode_antlr.loader import load_mcstas_instr
        return load_mcstas_instr(filepath)
    if suffix == '.json':
        from mccode_antlr.io.json import load_json
        return load_json(filepath)
    if suffix in ('.msgpack', '.mpk'):
        from mccode_antlr.io.msgpack import load_msgpack
        return load_msgpack(filepath)

    raise ValueError(f'Cannot load an instrument from {filepath.suffix} files')


def convert(argv=None):
    """Print the NeXus Structure JSON for an instrument file."""
    import argparse
    from json import dumps

    from .instrument import DEFAULT_NXLOG_ROOT, to_nexus_structure

    parser = argparse.ArgumentParser(
        description='Convert a McCode instrument to ESS NeXus Structure JSON'
    )
    parser.add_argument('filename', type=str, help='the instrument file to convert')
    parser.add_argument('--origin', type=str, default=None,
                        help='component to use as the coordinate origin '
                             '(default: the sample-category component)')
    parser.add_argument('--nxlog-root', type=str, default=DEFAULT_NXLOG_ROOT,
                        help='where runtime parameter values are published')
    parser.add_argument('--absolute-depends-on', action='store_true',
                        help='write depends_on targets as absolute NeXus paths')
    parser.add_argument('--indent', type=int, default=None,
                        help='indent the JSON by this many spaces')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='write to this file instead of standard output')
    args = parser.parse_args(argv)

    structure = to_nexus_structure(
        load_instr(args.filename),
        origin=args.origin,
        nxlog_root=args.nxlog_root,
        absolute_depends_on=args.absolute_depends_on,
    )
    text = dumps(structure, indent=args.indent)

    if args.output is None:
        print(text)
    else:
        Path(args.output).write_text(text + '\n')


if __name__ == '__main__':
    convert()
