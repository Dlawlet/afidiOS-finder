"""
Groq Model Manager
Rotates across multiple Groq models to maximize free-tier usage.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class GroqModelSpec:
    name: str
    quota: Optional[int] = None


class GroqModelManager:
    """
    Manage Groq model selection and rotation.

    Env vars:
      - GROQ_MODEL: default model name
      - GROQ_MODELS: comma-separated list, optionally with quotas
            Example: "llama-3.3-70b-versatile:1200,gemma2-9b-it:2000"
      - GROQ_MODEL_STRATEGY: "capacity" (default) or "round_robin"
    """

    def __init__(self):
        self.default_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.strategy = os.getenv("GROQ_MODEL_STRATEGY", "capacity")
        self.models = self._parse_models(os.getenv("GROQ_MODELS"))
        if not self.models:
            self.models = [GroqModelSpec(name=self.default_model, quota=None)]
        self.usage: Dict[str, int] = {m.name: 0 for m in self.models}
        self.disabled: set[str] = set()
        self._rr_index = 0

    def _parse_models(self, raw: Optional[str]) -> List[GroqModelSpec]:
        if not raw:
            return []
        models: List[GroqModelSpec] = []
        for entry in raw.split(','):
            entry = entry.strip()
            if not entry:
                continue
            if ':' in entry:
                name, quota_raw = entry.split(':', 1)
                name = name.strip()
                quota_raw = quota_raw.strip()
                try:
                    quota = int(quota_raw)
                except ValueError:
                    quota = None
                models.append(GroqModelSpec(name=name, quota=quota))
            else:
                models.append(GroqModelSpec(name=entry))
        return models

    def _remaining(self, model: GroqModelSpec) -> Optional[int]:
        if model.quota is None:
            return None
        return max(model.quota - self.usage.get(model.name, 0), 0)

    def pick_model(self) -> Optional[str]:
        candidates = [m for m in self.models if m.name not in self.disabled]
        if not candidates:
            return None

        # Filter by quota if set
        available = []
        for model in candidates:
            remaining = self._remaining(model)
            if remaining is None or remaining > 0:
                available.append(model)

        if not available:
            return None

        if self.strategy == "round_robin":
            model = available[self._rr_index % len(available)]
            self._rr_index += 1
            return model.name

        # capacity strategy: pick model with highest remaining quota
        def remaining_key(m: GroqModelSpec) -> int:
            remaining = self._remaining(m)
            return remaining if remaining is not None else 10 ** 9

        best = sorted(available, key=remaining_key, reverse=True)[0]
        return best.name

    def record_call(self, model_name: str):
        if model_name:
            self.usage[model_name] = self.usage.get(model_name, 0) + 1

    def disable_model(self, model_name: str):
        if model_name:
            self.disabled.add(model_name)

    def stats(self) -> Dict[str, Dict[str, Optional[int]]]:
        data: Dict[str, Dict[str, Optional[int]]] = {}
        for model in self.models:
            data[model.name] = {
                "quota": model.quota,
                "used": self.usage.get(model.name, 0),
                "remaining": self._remaining(model),
                "disabled": model.name in self.disabled,
            }
        return data
