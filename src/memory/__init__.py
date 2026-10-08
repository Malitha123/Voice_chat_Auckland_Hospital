"""Public API; provider dependencies load only when requested."""
from importlib import import_module

_EXPORTS = {'ConversationTurn': 'schemas', 'MemoryFact': 'schemas', 'ReminderIntent': 'schemas', 'Episode': 'schemas', 'Procedure': 'schemas', 'ShortTermStore': 'schemas', 'LongTermStore': 'schemas', 'Embedder': 'schemas', 'Clock': 'schemas', 'ShortTermMemoryStore': 'st_store', 'LongTermMemoryStore': 'lt_store', 'EpisodicMemoryStore': 'episodic_store', 'create_episode_from_turns': 'episodic_store', 'ProceduralMemoryStore': 'procedural_store', 'MemoryDistiller': 'memory_ops', 'MemoryRecaller': 'memory_ops', 'MemoryForgetService': 'memory_ops'}
__all__ = list(_EXPORTS)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value
