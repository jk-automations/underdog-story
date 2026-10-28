"""Underdog Story for ComfyUI: a business owner's underdog story, written, drawn and animated with ComfyUI partner
nodes (Gemini, Nano Banana 2, Veo 3.1), cut into one share-ready vertical film. Clone into ComfyUI/custom_nodes/. Apache-2.0."""
from pathlib import Path

if __package__:  # loaded by ComfyUI as a custom node pack (pytest imports this file without a package)
    from .underdog_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
else:
    NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = {}, {}

BLANK = "underdog_blank.png"

# Unused reference slots still need a file: put a flat placeholder into input/ (the Scene node skips flat images).
try:
    if not __package__:
        raise ImportError("not running inside ComfyUI")
    import folder_paths
    from PIL import Image
    _blank = Path(folder_paths.get_input_directory()) / BLANK
    if not _blank.exists():
        _blank.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (255, 255, 255)).save(_blank)
except Exception as e:  # never block ComfyUI start-up
    print(f"[Underdog Story] could not place the blank placeholder: {e}")

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
