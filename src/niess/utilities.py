from scipp import Variable


def is_type(x, t, name):
    if not isinstance(x, t):
        raise RuntimeError(f"{name} must be a {t}")


def has_compatible_unit(x: Variable, unit):
    from scipp import UnitError
    try:
        x.to(unit=unit, copy=False)
    except UnitError:
        return False
    return True


def is_scalar(x: Variable):
    from scipp import DimensionError
    try:
        y = x.value
    except DimensionError:
        return False
    return True

