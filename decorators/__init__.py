from functools import reduce


def pipe(*args):
    """
    A Haskell-like: 5 & (+1) & (+1) -> 7
    """
    return lambda val: reduce(lambda prev, fn: fn(prev), args, val)


def negate(fn):
    """
    A decorator to negate function call result.
    """
    def wrap(*args, **kwargs):
        return not bool(fn(*args, **kwargs))

    return wrap


def flip(fn):
    """
    A flip combinator decorator.
    """
    def wrap(*args, **kwargs):
        return fn(*reversed(args), **kwargs)

    return wrap


def catching(exceptions, message="", exit_code=1, ignoring=False):
    """
    A decorator to catch exceptions either to exit or mute them.
    """
    def decorator(fn):
        def wrap(*args, **kwargs):
            try:
                return fn(*args, **kwargs)

            except exceptions:
                print(message)
                if not ignoring:
                    exit(exit_code)

        return wrap
    return decorator

