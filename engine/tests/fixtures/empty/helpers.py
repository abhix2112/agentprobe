"""A repo with no agent at all — introspection must return 422, not guess."""


def add(a, b):
    return a + b


CONSTANT = "just some module, no agent here"
