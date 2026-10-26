from __future__ import annotations

PLUGIN_ID = "llm_provider"

DEFAULT_CONFIG = {
    "queue": {
        "max_recent_jobs": 100,
    },
    "routing": {},
    "providers": {},
}

TIER_VALUES = ("t1", "t2", "t3", "vl", "eb")
TIER_ALIASES = {
    "t1": "t1",
    "t2": "t2",
    "t3": "t3",
    "vl": "vl",
    "vision": "vl",
    "embedding": "eb",
    "embeddings": "eb",
    "eb": "eb",
}
