# Command line

niess installs one command.

## `instr2ns`

Convert a McCode instrument to ESS NeXus Structure JSON.

```console
$ instr2ns INSTRUMENT [options]
```

`INSTRUMENT` may be a McStas `.instr` file, or an instrument serialised as `.json`,
`.msgpack` or `.mpk`.

| option | default | effect |
| --- | --- | --- |
| `--origin NAME` | the sample-category component | the component whose frame everything is placed against |
| `--registry MODULE:NAME` | the generic translators | an instrument-specific translator registry |
| `--nxlog-root PATH` | `/entry/parameters` | where run-time parameter values are published |
| `--absolute-depends-on` | off | write `depends_on` targets as absolute NeXus paths |
| `--indent N` | compact | pretty-print the JSON |
| `-o`, `--output FILE` | standard output | write to a file |

Without `--origin`, niess looks for a component of McStas category `samples`; if there
is none it warns and falls back to absolute positions.

`--registry` takes an importable module and the name of a registry in it:

```console
$ instr2ns bifrost.json --origin sample_origin \
    --registry niess.nexus.bifrost:BIFROST_REGISTRY
```

Without it, component types only that registry knows fall back to a generic class — for
BIFROST that means its 45 analyzers and 45 detector triplets become
`NXcoordinate_system` groups. They are still placed correctly; they are just not
classified.
