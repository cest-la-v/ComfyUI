HOW TO RUN
==========

Double-click start.bat at the portable root — it shows a menu:

  [1] Launch normally                (default)
  [2] Launch — disable smart memory  (try if you get OOM errors)
  [3] Launch — local frontend build  (dev only)
  [4] Upgrade ROCm/PyTorch packages, then launch
  [5] Update ComfyUI source (git pull), then launch
  [6] Update source + upgrade ROCm, then launch
  [Q] Quit

Command-line flags skip the menu (combinable):
  start.bat --upgrade
  start.bat --update --upgrade
  start.bat --update --upgrade --no-launch
  start.bat --local-frontend --no-smart-mem


SCRIPTS IN THIS FOLDER
========================

  run_amd_gpu.bat    — canonical launcher (called by start.bat shim)
  fetch_rocm_urls.py — scrapes repo.radeon.com, prints ROCm wheel URLs to stdout
  update_amd_deps.bat — standalone update + upgrade without launching


ENVIRONMENT VARIABLE OVERRIDES
================================
Set before calling to override defaults:

  PORTABLE_ROOT   Root of the portable package
  PYTHON          Path to python.exe
  COMFYUI_ROOT    Path to the ComfyUI git repo
  FRONTEND_ROOT   Path to the built frontend dist folder


IF YOU GET A RED ERROR IN THE UI
==================================
Make sure you have a model in:  ComfyUI\models\checkpoints

Stable Diffusion XL:
https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/sd_xl_base_1.0_0.9vae.safetensors


TO SHARE MODELS WITH ANOTHER UI
==================================
Edit:  ComfyUI\extra_model_paths.yaml
(copy from extra_model_paths.yaml.example if it doesn't exist)


DRIVER
=======
Latest AMD driver: https://www.amd.com/en/support/download/drivers.html
