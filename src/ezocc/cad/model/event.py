from enum import Enum


class SessionEventType(Enum):
    CREATED = 0
    UPDATED = 1
    DESTROYED = 2
    INDIRECT = 3


class SessionEvent:

    def __init__(self,
                 target,
                 type: SessionEventType):
        self._target = target
        self._type = type

    @property
    def target(self):
        return self._target

    @property
    def type(self):
        return self._type


class ListenerManager:

    def __init__(self):
        self._listeners = set()

    def add_listener(self, l):
        if l in self._listeners:
            raise ValueError("Duplicate entry.")

        self._listeners.add(l)

    def remove_listener(self, l):
        if l not in self._listeners:
            raise ValueError("Listener not present")

        self._listeners.remove(l)

    def notify(self, session_event: SessionEvent):
        if not isinstance(session_event, SessionEvent):
            raise ValueError("Please send session events.")

        for l in self._listeners:
            l(session_event)


class Listenable:

    def __init__(self):
        self.listener_manager = ListenerManager()
