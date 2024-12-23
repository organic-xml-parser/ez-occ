import logging

logger = logging.getLogger(__name__)

def unstable(func):

    def _wrapper(*args, **kwargs):

        """
        Indicates that a function or class is undergoing development and should be used with care.
        """
        logger.warning(f"Function {func.__module__ + '.' + func.__qualname__} is unstable and should not be relied upon for consistent output.")
        return func(*args, **kwargs)

    return _wrapper