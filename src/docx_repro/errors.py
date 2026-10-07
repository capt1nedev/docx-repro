class ReproError(Exception):
    """A user-facing input, checker, or output error."""


class InputError(ReproError):
    pass


class CheckError(ReproError):
    pass


class CheckLimit(Exception):
    """Internal signal to finish with the best confirmed candidate."""
