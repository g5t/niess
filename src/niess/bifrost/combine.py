from scipp import Variable


def combine_parameters(objs, sample: Variable):
    """To be used internally by Tank and Channel classes

    Parameters
    ----------
    objs:
        An iterable of objects, each which has a `mcstas_parameters` method
        that returns a dictionary of parameters, including at least the keys
        'distance', 'analyzer', 'detector', 'two_theta'
    """
    from numpy import stack
    parameters = [obj.mcstas_parameters(sample) for obj in objs]
    # switch from a list of dictionaries to a dictionary of arrays
    keys = 'distances', 'analyzer', 'detector', 'two_theta'
    return {k: stack([p[k] for p in parameters], axis=0) for k in keys}
