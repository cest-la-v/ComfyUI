# AGENTS.md

> Technical reference for the **cest-la-v/ComfyUI** fork.
> Read by GitHub Copilot (Chat + CLI), VS Code, and other AI agents.
> Human-readable intro lives in `README.md`.

---

## Project Overview

ComfyUI is a **node-based AI image/video generation backend** with a WebSocket/HTTP server. This is a personal fork of `comfyanonymous/ComfyUI` with bug fixes and feature additions maintained on separate branches (see [Fork Feature Branches](#fork-feature-branches) below).

### High-level architecture

```
server.py (PromptServer / aiohttp)
    ↓ queues prompt JSON
execution.py (PromptExecutor)
    ↓ builds DynamicPrompt (DAG), resolves execution order
comfy_execution/  — graph.py, caching.py, validation.py, jobs.py, progress.py
    ↓ calls node.execute() per node
nodes.py + comfy_extras/ + comfy_api_nodes/ + custom_nodes/
    ↓ uses ML primitives
comfy/  — model_management.py, samplers.py, sd.py, lora.py, controlnet.py, …
```

| Package | Purpose |
|---|---|
| `comfy/` | Pure ML: model loading/patching, samplers, CLIP, VAE, ControlNet, LoRA, memory management. No server/node logic. |
| `comfy_execution/` | Graph parsing, cache backends (Hierarchical, LRU, RAMPressure, Null), job tracking, lazy evaluation, progress reporting. |
| `nodes.py` | All built-in node class definitions. Registers into `NODE_CLASS_MAPPINGS`. |
| `comfy_api_nodes/` | Official third-party service integrations (BFL, Gemini, Kling, Luma, OpenAI, ElevenLabs, …), one file per service: `nodes_<service>.py`. Pylint runs on this package in CI. |
| `comfy_api/` | Versioned public Python API (`latest/`, `v0_0_1/`, `v0_0_2/`). `comfy_api/latest/` is the preferred API. |
| `folder_paths.py` | Central registry mapping model categories to filesystem paths. |
| `app/` | UserManager, ModelFileManager, CustomNodeManager, SubgraphManager, NodeReplaceManager, asset seeder. |
| `api_server/` | REST routes (separate from `server.py`'s WebSocket routes). |
| `server.py` | `PromptServer` singleton: WebSocket, HTTP routes, queue, history, progress broadcasting. |

---

## Setup Commands

```bash
# Install Python deps
pip install -r requirements.txt

# Unit test deps
pip install -r tests-unit/requirements.txt

# Start the server
python main.py
```

---

## Testing Instructions

```bash
# Unit tests — fast, no GPU, no running server
python -m pytest tests-unit/

# Single unit test
python -m pytest tests-unit/<folder>/<file>.py::test_function_name -v

# Integration / execution tests (requires a running ComfyUI server)
python -m pytest tests/execution/ -v --skip-timing-checks

# Inference / quality tests (requires GPU)
python -m pytest -m inference tests/inference/
```

`pytest.ini` markers: `inference`, `execution` — skip with `-m "not inference"`.
`addopts = -s` means stdout is always shown; `pythonpath = .` is pre-set.

---

## Linting

```bash
# Primary linter (all packages except comfy_api_nodes)
ruff check .

# Pylint — runs ONLY on comfy_api_nodes/
pylint comfy_api_nodes
```

**Ruff rules enforced:** `E`/`W` (pycodestyle), `F` (pyflakes), `T` (print statements → use `logging` instead), `N805` (bad `cls` arg), `S307`/`S102` (eval/exec).  
**Ignored:** `E501` (line length), `E722` (bare except), `E402` (import order), `E741` (ambiguous names).

---

## Code Style Guidelines

- **`from __future__ import annotations`** is used in almost every file (PEP 563 deferred evaluation).
- **`typing_extensions`** for `NotRequired`, `override`, etc. — available pre-3.11.
- Tensor shapes: **`[B, H, W, C]`** channel-last (not PyTorch's `[B, C, H, W]`).
- `print()` triggers a Ruff `T` warning — always use `logging`.
- Generated files under `**/generated/` are auto-generated from OpenAPI specs — **do not hand-edit**.
- `comfy_api_nodes/apis/<service>.py` — API client helpers, often auto-generated.
- `comfy_api_nodes/util/client.py` — provides `sync_op`/`poll_op`/`ApiEndpoint` helpers for wrapping async service calls in nodes.
- `PromptServer.instance` singleton is accessible anywhere after startup — nodes use it for WebSocket broadcasting or registering extra routes.

---

## Node Authoring

### Modern API (preferred for new nodes)

```python
from comfy_api.latest import io
from typing_extensions import override

class MyNode(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MyNamespace_MyNode",
            display_name="My Node",
            category="mycat",
            inputs=[
                io.Image.Input("image"),
                io.Float.Input("strength", default=1.0, min=0.0, max=1.0),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    @override
    def execute(cls, image, strength) -> io.NodeOutput:
        return io.NodeOutput(process(image, strength))
```

### Legacy API (nodes.py style — still widely used)

```python
class MyNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": { "image": ("IMAGE",), "strength": ("FLOAT", {"min": 0.0, "max": 1.0, "step": 0.01}) },
            "optional": { "mask": ("MASK",) },
            "hidden":   { "unique_id": ("UNIQUE_ID",) },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "image"
    OUTPUT_NODE = True       # marks this as a sink / output node
    INPUT_IS_LIST = True     # receive batched inputs as a list
    OUTPUT_IS_LIST = (True,) # emit a list for downstream nodes
    DEPRECATED = True        # hide from the UI add-node menu

    def execute(self, image, strength, mask=None, unique_id=None):
        return (result,)

    @classmethod
    def IS_CHANGED(cls, image, strength, **kwargs):
        import hashlib
        return hashlib.md5(image).hexdigest()  # force re-execution when hash changes

NODE_CLASS_MAPPINGS         = { "MyNode": MyNode }
NODE_DISPLAY_NAME_MAPPINGS  = { "MyNode": "My Node (Display)" }
```

### Cache invalidation

- Modern API: override `fingerprint_inputs(cls, **kwargs)`.
- Legacy API: define `IS_CHANGED(cls, **inputs)` — return a value that changes when the node must re-run.

### Lazy / deferred inputs

Use `check_lazy_status()` (legacy) or `io.LazyInput` (modern) to avoid executing upstream nodes whose outputs you may not need.

### IO type constants

Use `IO.*` from `comfy.comfy_types` (legacy) or `io.*` from `comfy_api.latest`:

`IMAGE`, `MASK`, `LATENT`, `CONDITIONING`, `MODEL`, `CLIP`, `VAE`, `CONTROL_NET`, `AUDIO`, `VIDEO`, `STRING`, `INT`, `FLOAT`, `BOOLEAN`, `COMBO`, `SAMPLER`, `SIGMAS`, `GUIDER`, `NOISE`, `UPSCALE_MODEL`, `LORA_MODEL`, `CLIP_VISION`, `CLIP_VISION_OUTPUT`

Special: `IO.ANY = "*"` (matches everything, use sparingly), `IO.NUMBER = "FLOAT,INT"`, `IO.PRIMITIVE = "STRING,FLOAT,INT,BOOLEAN"`.

---

## Prompt / Graph Format

A "prompt" is a JSON object mapping string node IDs to node descriptors:

```json
{
  "1": { "class_type": "CheckpointLoaderSimple", "inputs": { "ckpt_name": "model.safetensors" } },
  "2": { "class_type": "CLIPTextEncode",         "inputs": { "clip": ["1", 1], "text": "a cat" } },
  "3": { "class_type": "KSampler",               "inputs": { "model": ["1", 0], "positive": ["2", 0], "seed": 42 } }
}
```

A link is `[node_id, output_index]`. `DynamicPrompt` wraps this dict and supports ephemeral nodes created at runtime by subgraph expansion.

---

## Fork Feature Branches

Feature and fix work is maintained on separate branches off `upstream/master`. `dev` carries only repo housekeeping and docs.

| Branch | What it contains | Upstream PR |
|---|---|---|
| `feat/generation-metadata` | A1111-compatible generation metadata pipeline (`comfy_execution/generation_context.py`, `SaveImage` integration) | Fork-only |
| `feat/extra-paths-config` | Generic `extra_paths.yaml` config: system dirs, `custom_nodes`, nested `models:` sub-block, auto-scan, backward-compat with `extra_model_paths.yaml`; fixes `custom_nodes` implicit-scan bug | Fork-only (upstream candidate) |
| `fix/files-api-recursive-scan` | `GET /files/{type}` made recursive via `os.walk` | Candidate — no PR yet |
| `fix/guard-unregistered-class-type` | `.get()` safety fix in `_is_intermediate_output` to prevent `KeyError` on orphan nodes | [PR #13552](https://github.com/Comfy-Org/ComfyUI/pull/13552) |

### Coding rule: NODE_CLASS_MAPPINGS lookups

Always use `.get()` with a `None` guard when looking up a `class_type` in `NODE_CLASS_MAPPINGS` if the node ID has not been validated:

```python
# Good
node_class = NODE_CLASS_MAPPINGS.get(class_type)
if node_class is None:
    ...

# Bad — KeyError if a custom node failed to load
node_class = NODE_CLASS_MAPPINGS[class_type]
```

A `KeyError` in `_is_intermediate_output` short-circuits the `while…else` block, preventing `execution_success` from reaching the frontend even though images were already saved.

---

## Testing Patterns

| Layer | Location | Notes |
|---|---|---|
| Unit | `tests-unit/` | Fast, no GPU, no server. Each subdir mirrors the package (e.g. `comfy_execution_test/`). |
| Integration | `tests/execution/` | Needs a live server. Use `--skip-timing-checks` locally. |
| Inference/quality | `tests/inference/` | Needs GPU. Compares images to a baseline directory. |

---

## PR Guidelines

- Commit message format: `type: short description` (e.g. `feat:`, `fix:`, `chore:`).
- Always include the Copilot co-author trailer when Copilot contributed:
  ```
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
  ```
- Run `ruff check .` and `python -m pytest tests-unit/` before committing.
- For `comfy_api_nodes/` changes, also run `pylint comfy_api_nodes`.
