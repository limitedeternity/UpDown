from functools import reduce


def pipe(*args):
    return lambda val: reduce(lambda prev, fn: fn(prev), args, val)


def negate(fn):
    def wrap(*args, **kwargs):
        return not bool(fn(*args, **kwargs))

    return wrap


def flip(fn):
    def wrap(*args, **kwargs):
        return fn(*reversed(args), **kwargs)

    return wrap


def catching(exceptions, message="", exit_code=1, ignoring=False):
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

