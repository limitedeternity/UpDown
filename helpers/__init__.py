from datetime import datetime, timedelta
from threading import Event, Thread

class Call:
    """
    A helper class to wrap a function call.
    Accepts a function and its arguments on init and applies them on call.
    """
    def __init__(self, fn, *args, **kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *ignored_args, **ignored_kwargs):
        return self.fn(*self.args, **self.kwargs)


class AttributeDict(dict):
    """
    Convert a simple dictionary to a class with attributes.
    A hack to achieve JS-like dictionary entry access using dot-notation.
    """
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class Chain:
    """
    A helper class to explicitly declare a sequence of function calls in a functional way.
    """
    def __init__(self, starting_function, *args, **kwargs):
        self.current_function = starting_function
        self.args = args
        self.kwargs = kwargs
        self.callables = []

    def prepare_to_switch(self):
        self.callables.append(Call(self.current_function, *self.args, **self.kwargs))
        self.args = []
        self.kwargs = {}

    def then(self, next_fn, *args, **kwargs):
        """
        Chaining method
        """
        self.prepare_to_switch()
        self.current_function = next_fn
        self.args = args
        self.kwargs = kwargs
        return self

    def execute(self):
        """
        Call this function to make some magic.
        """
        self.prepare_to_switch()
        for fn in self.callables:
            fn()


def Conditional(condition, *cond_args, **cond_kwargs):
    """
    This is a helper __function__ to declare conditional operations in a functional way.
    Accepts a condition as a function and its arguments.
    .then() accepts a function (or maybe a Chain) with arguments. Executes if the condition is True.
    .otherwise() is the same as .then(), but executes if the condition is False.
    If you don't want/need to specify .otherwise(), you may call .end() after .then().
    """
    def then(fn, *args, **kwargs):
        if condition(*cond_args, **cond_kwargs):
            def guarding_identity(val):
                def wrap(*ignored_args, **ignored_kwargs):
                    return val

                return wrap

            result = Call(fn, *args, **kwargs)
            return AttributeDict({"otherwise": guarding_identity(result), "end": guarding_identity(result)})

        else:
            def otherwise(fn, *o_args, **o_kwargs):
                return Call(fn, *o_args, **o_kwargs)

            def do_nothing(*ignored_args, **ignored_kwargs):
                return Call(do_nothing)

            return AttributeDict({"otherwise": otherwise, "end": do_nothing})

    return AttributeDict({"then": then})


class setInterval:
    """
    A JS-like setInterval implementation.
    This class accepts a function (or maybe a Call), an interval in seconds and "immediately" flag.
    Creates a daemonized thread which calls a function every $(interval) seconds.
    Can be .cancel()'ed.
    """
    def __init__(self, func, interval, immediately=False):
        self.func = func
        self.interval = interval
        self.immediately = immediately
        self.stop_event = Event()

        t = Thread(target=self._run)
        t.daemon = True
        t.start()

    def _run(self):
        if self.immediately:
            self.func()

        next_time = datetime.now() + timedelta(seconds=self.interval)
        while not self.stop_event.wait((next_time - datetime.now()).total_seconds()):
            next_time += timedelta(seconds=self.interval)
            self.func()

    def cancel(self):
        if not self.stop_event.is_set():
            self.stop_event.set()

