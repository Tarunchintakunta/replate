# ADR 002 — OpenCV and LaMa

Status: accepted

Fast mode is OpenCV TELEA. It is always installed and is the right tool for flat paper. AI mode is the LaMa TorchScript checkpoint `big-lama.pt`, loaded with `torch.jit.load` on CPU or CUDA after a SHA-256 check. Auto mode picks from the background complexity of the ring around the text.

Diffusion models were rejected for CPU time and weight size. A solid rectangle fill was rejected because it frames the edit on any non-flat background.

If LaMa is absent or fails, the edit uses OpenCV and the API returns `fallback_reason`. The app does not pretend the AI model ran.

LaMa is applied to a crop around the mask, not the whole page, so a line of text does not require a full-page forward pass.
