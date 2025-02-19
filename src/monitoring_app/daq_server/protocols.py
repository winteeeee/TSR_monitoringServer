import io
import pickle
from enum import Enum, auto
from typing import Tuple


MSG_SEP_TOKEN = '.'


class ProtocolException(Exception):
    pass


class DAQEvent(Enum):
    CONNECT: int = auto()
    DISCONNECT: int = auto()
    MESSAGE: int = auto()


def send_protocol(event: DAQEvent, machine_name: str, machine_msg: Tuple[str, object] = None):
    try:
        with io.BytesIO() as memfile:
            pickle.dump((event, machine_name, machine_msg), memfile)
            serialized = memfile.getvalue()
    except Exception:
        raise ProtocolException()
    return serialized


def recv_protocol(msg: bytes):
    try:
        with io.BytesIO() as memfile:
            memfile.write(msg)
            memfile.seek(0)
            tcp_event, machine_name, machine_msg = pickle.load(memfile)
    except Exception:
        raise ProtocolException()
    return tcp_event, machine_name, machine_msg


def tcp_recv_protocol(msg: bytes):
    try:
        with io.BytesIO() as memfile:
            memfile.write(msg)
            memfile.seek(0)
            event, data = pickle.load(memfile)
    except Exception:
        raise ProtocolException()
    return event, data
