"""Public API; provider dependencies load only when requested."""
from importlib import import_module

_EXPORTS = {'get_chat_llm': 'llm', 'get_default_embeddings': 'llm', 'observe': 'observability', 'flush': 'observability', 'get_langfuse': 'observability'}
__all__ = list(_EXPORTS)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value
