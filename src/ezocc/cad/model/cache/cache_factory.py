import os
import sys
import tempfile
import uuid

from ezocc.cad.model.cache.file_based_session_cache import FileBasedSessionCache
from ezocc.cad.model.cache.session_cache import SessionCache


class CallCountTracker:
    """
    Hacky way to handle multiple previews from a single python file.
    Sometimes preview() will be used multiple times, for example to show progress.
    In these cases we would like to try and preserve the camera orientations etc.
    that were in use in each of these calls. This won't work 100%, e.g. if the user
    adds/removes preview() calls but should usually be helpful
    """
    CACHE_GENERATE_CALL_COUNT = 0


def create_session_cache() -> SessionCache:
    # attempt to generate a process specific file
    system_temp_dir = tempfile.gettempdir()
    cache_file_name = str(uuid.uuid5(uuid.NAMESPACE_URL, sys.argv[0] + str(CallCountTracker.CACHE_GENERATE_CALL_COUNT))) + '.json'

    cache = FileBasedSessionCache(os.path.join(system_temp_dir, cache_file_name))

    CallCountTracker.CACHE_GENERATE_CALL_COUNT += 1

    return cache
