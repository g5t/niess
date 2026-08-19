"""Underscore-prefixed Section fields are per-class extras, invisible to introspection.

`_flat` controls how a Section inserts itself into an Assembler, and a subclass may add
any number of others. None of them is a component, so `parts()`, `types()`, `items()`
and `field_types()` must all agree in ignoring them -- however many there are and
wherever they are declared.

`types()` used to return every field while `parts()` filtered, so `items()` zipped a
short list against a long one. That happened to work only while a single extra was
declared last, which is a constraint msgspec already imposes for its own reasons.
"""
import msgspec
import pytest

from niess.components import Component, Section
from niess.components.guide import StraightGuide


class OneExtra(Section):
    a: Component
    b: StraightGuide
    _flat: bool = True


class SeveralExtras(Section):
    a: Component
    b: StraightGuide
    _flat: bool = False
    _label: str = 'anything'
    _count: int = 3


@pytest.mark.parametrize('section', [OneExtra, SeveralExtras],
                         ids=['one_extra', 'several_extras'])
def test_extras_are_invisible_to_introspection(section):
    assert section.parts() == ['a', 'b']
    assert section.types() == [Component, StraightGuide]
    assert section.items() == [('a', Component), ('b', StraightGuide)]
    assert section.field_types() == {'a': Component, 'b': StraightGuide}


@pytest.mark.parametrize('section', [OneExtra, SeveralExtras],
                         ids=['one_extra', 'several_extras'])
def test_names_and_types_stay_aligned(section):
    """The failure mode: items() pairing a name with the next field's type."""
    assert len(section.parts()) == len(section.types())
    for name, kind in section.items():
        assert section.field_types()[name] is kind


def defaults(section):
    """The declared default of every field, extras included."""
    return {f.name: f.default for f in msgspec.structs.fields(section)}


def test_extras_still_carry_their_values():
    """Being invisible to introspection does not mean being absent."""
    assert defaults(OneExtra)['_flat'] is True
    assert defaults(SeveralExtras)['_flat'] is False
    assert defaults(SeveralExtras)['_count'] == 3


def test_a_defaulted_field_must_follow_the_required_ones():
    """Why _flat is declared last: msgspec's rule, not niess's.

    A Section's extras carry defaults, and msgspec refuses a required field after an
    optional one unless the struct is kw_only.
    """
    with pytest.raises(TypeError, match='cannot follow optional fields'):
        class DefaultFirst(Section):
            _flat: bool = True
            a: Component
