"""
Generation Metadata Context — forward-propagating per-node context that accumulates
generation parameters as execution walks the graph in topological order.

Usage (custom node authors):
    from comfy_execution.generation_context import set_generation_metadata

    class MySampler:
        def execute(self, steps, cfg, sampler_name, seed, ...):
            set_generation_metadata(steps=steps, cfg_scale=cfg, sampler=sampler_name, seed=seed)
            # ... actual work
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from comfy_execution.graph import DynamicPrompt

from comfy_execution.graph_utils import is_link

# ---------------------------------------------------------------------------
# Role-assignment hint tables (no class-type knowledge needed)
# ---------------------------------------------------------------------------

# Inputs whose upstream _pending_text becomes positive_prompt
POSITIVE_ROLE_INPUTS: frozenset[str] = frozenset({
    'positive', 'pos', 'conditioning_positive',
})

# Inputs whose upstream _pending_text becomes negative_prompt
NEGATIVE_ROLE_INPUTS: frozenset[str] = frozenset({
    'negative', 'neg', 'conditioning_negative',
})

# Inputs whose literal string value is stored as _pending_text
TEXT_INPUTS: frozenset[str] = frozenset({
    'text', 'prompt', 'value', 'string',
})

# Inputs that map directly to a GenerationMetadata field.
# '_lora_append' is a special sentinel meaning append to loras list.
DIRECT_FIELD_INPUTS: Dict[str, str] = {
    'steps': 'steps',
    'cfg': 'cfg_scale',
    'cfg_scale': 'cfg_scale',
    'sampler_name': 'sampler',
    'scheduler': 'scheduler',
    'seed': 'seed',
    'noise_seed': 'seed',
    'ckpt_name': 'model',
    'lora_name': '_lora_append',
}

# ---------------------------------------------------------------------------
# GenerationMetadata dataclass
# ---------------------------------------------------------------------------

@dataclass
class GenerationMetadata:
    """Accumulated generation parameters for one branch of the execution graph."""

    positive_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    _pending_text: Optional[str] = None  # text not yet assigned a role
    model: Optional[str] = None
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    seed: Optional[int] = None
    loras: list = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            self.positive_prompt is None
            and self.negative_prompt is None
            and self.model is None
            and self.sampler is None
            and self.scheduler is None
            and self.steps is None
            and self.cfg_scale is None
            and self.seed is None
            and not self.loras
        )

    def merge(self, other: 'GenerationMetadata') -> 'GenerationMetadata':
        """Return a new metadata that merges self with other. Other's non-None values win."""
        def _pick(a, b):
            return b if b is not None else a

        return GenerationMetadata(
            positive_prompt=_pick(self.positive_prompt, other.positive_prompt),
            negative_prompt=_pick(self.negative_prompt, other.negative_prompt),
            _pending_text=_pick(self._pending_text, other._pending_text),
            model=_pick(self.model, other.model),
            sampler=_pick(self.sampler, other.sampler),
            scheduler=_pick(self.scheduler, other.scheduler),
            steps=_pick(self.steps, other.steps),
            cfg_scale=_pick(self.cfg_scale, other.cfg_scale),
            seed=_pick(self.seed, other.seed),
            loras=list(dict.fromkeys(self.loras + other.loras)),  # deduplicate preserving order
        )



# ---------------------------------------------------------------------------
# Context computation (pure function, called per node before cache check)
# ---------------------------------------------------------------------------

def compute_node_context(
    unique_id: str,
    raw_inputs: Dict[str, Any],
    registry: 'GenerationContextRegistry',
) -> 'GenerationMetadata':
    """
    Compute the GenerationMetadata for a node from its raw inputs dict and the
    already-computed contexts of its upstream nodes.

    This is a pure function of the graph structure — it runs before the cache
    check so even cached nodes accumulate context for downstream nodes.
    """
    ctx = GenerationMetadata()

    for input_name, value in raw_inputs.items():
        if is_link(value):
            source_id = value[0]
            upstream = registry.get_context(source_id)
            if upstream is None:
                continue

            if input_name in POSITIVE_ROLE_INPUTS:
                # Promote pending text to positive prompt
                promoted = upstream._pending_text or upstream.positive_prompt
                if promoted is not None:
                    ctx.positive_prompt = promoted
                # Merge everything else (model, sampler, etc.)
                ctx = _merge_non_text(ctx, upstream)

            elif input_name in NEGATIVE_ROLE_INPUTS:
                # Promote pending text to negative prompt
                promoted = upstream._pending_text or upstream.negative_prompt
                if promoted is not None:
                    ctx.negative_prompt = promoted
                ctx = _merge_non_text(ctx, upstream)

            else:
                # Generic link — merge the full upstream context
                ctx = ctx.merge(upstream)

        elif isinstance(value, (str, int, float)):
            # Literal value — map by input name
            if input_name in TEXT_INPUTS and isinstance(value, str):
                ctx._pending_text = value

            elif input_name in DIRECT_FIELD_INPUTS:
                field_name = DIRECT_FIELD_INPUTS[input_name]
                if field_name == '_lora_append':
                    if isinstance(value, str) and value not in ctx.loras:
                        ctx.loras.append(value)
                else:
                    # Type coerce: steps/seed → int, cfg_scale → float, others → str
                    if field_name in ('steps', 'seed'):
                        try:
                            value = int(value)
                        except (ValueError, TypeError):
                            continue
                    elif field_name == 'cfg_scale':
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            continue
                    setattr(ctx, field_name, value)

    return ctx


def _merge_non_text(ctx: GenerationMetadata, other: GenerationMetadata) -> GenerationMetadata:
    """Merge non-prompt fields from other into ctx (other wins on conflicts)."""
    def _pick(a, b):
        return b if b is not None else a

    return GenerationMetadata(
        positive_prompt=ctx.positive_prompt,
        negative_prompt=ctx.negative_prompt,
        _pending_text=ctx._pending_text,
        model=_pick(ctx.model, other.model),
        sampler=_pick(ctx.sampler, other.sampler),
        scheduler=_pick(ctx.scheduler, other.scheduler),
        steps=_pick(ctx.steps, other.steps),
        cfg_scale=_pick(ctx.cfg_scale, other.cfg_scale),
        seed=_pick(ctx.seed, other.seed),
        loras=list(dict.fromkeys(ctx.loras + other.loras)),
    )


# ---------------------------------------------------------------------------
# GenerationContextRegistry (global singleton, reset per execution)
# ---------------------------------------------------------------------------

class GenerationContextRegistry:
    """
    Stores one GenerationMetadata per node ID. Reset at the start of each prompt
    execution (mirrors the ProgressRegistry pattern).
    """

    def __init__(self):
        self._contexts: Dict[str, GenerationMetadata] = {}

    def get_context(self, node_id: str) -> Optional[GenerationMetadata]:
        return self._contexts.get(node_id)

    def set_context(self, node_id: str, ctx: GenerationMetadata) -> None:
        self._contexts[node_id] = ctx

    def clear(self) -> None:
        self._contexts.clear()


# Global singleton
_global_generation_registry: Optional[GenerationContextRegistry] = None


def reset_generation_context() -> None:
    """Reset the global registry. Called at the start of each prompt execution."""
    global _global_generation_registry
    if _global_generation_registry is not None:
        _global_generation_registry.clear()
    else:
        _global_generation_registry = GenerationContextRegistry()


def get_generation_registry() -> GenerationContextRegistry:
    global _global_generation_registry
    if _global_generation_registry is None:
        _global_generation_registry = GenerationContextRegistry()
    return _global_generation_registry


# ---------------------------------------------------------------------------
# Public override API for custom node authors
# ---------------------------------------------------------------------------

def set_generation_metadata(**kwargs) -> None:
    """
    Override auto-detected generation metadata for the currently executing node.
    Call from within a node's execute() method.

    Supported kwargs: positive_prompt, negative_prompt, model, sampler, scheduler,
                      steps, cfg_scale, seed, loras (list of str)

    Example:
        from comfy_execution.generation_context import set_generation_metadata

        class MySampler:
            def execute(self, steps, cfg, sampler_name, seed, ...):
                set_generation_metadata(steps=steps, cfg_scale=cfg,
                                        sampler=sampler_name, seed=seed)
    """
    from comfy_execution.utils import get_executing_context

    exec_ctx = get_executing_context()
    if exec_ctx is None:
        return

    node_id = exec_ctx.node_id
    registry = get_generation_registry()
    existing = registry.get_context(node_id) or GenerationMetadata()

    for key, value in kwargs.items():
        if hasattr(existing, key) and value is not None:
            setattr(existing, key, value)

    registry.set_context(node_id, existing)
