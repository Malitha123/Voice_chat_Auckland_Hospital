"""Public API; provider dependencies load only when requested."""
from importlib import import_module

_EXPORTS = {'VoiceConfig': 'config', 'load_voice_config': 'config', 'validate_voice_env': 'config', 'LangGraphLLMAdapter': 'adapter', 'build_voice_agent': 'agent', 'create_and_start_agent': 'agent', 'SessionManager': 'pipeline', 'VoiceSession': 'pipeline'}
__all__ = list(_EXPORTS)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value
