---
name: local-llm-hardware
description: "Evaluate and compare laptops/desktops for local LLM inference: GPU VRAM tiers, CPU fallback, model size limits, and buying guidance."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [local-llm, hardware, gpu, vram, inference, laptop, benchmark]
---

# Local LLM Hardware Selection

How to evaluate hardware for running local LLMs, and how to compare specific listings.

---

## The One Number That Matters: GPU VRAM

For local LLM inference, **dedicated GPU VRAM** is the primary bottleneck. Everything else is secondary.

| VRAM | What you can run | Speed |
|------|-----------------|-------|
| 0 (integrated / shared) | 7B Q4 via CPU (llama.cpp AVX2) | 2–5 tok/s |
| 4 GB dedicated (GTX 1050, GTX 1650) | 7B Q4 fully in VRAM | 15–25 tok/s |
| 6 GB (RTX 3060 mobile) | 7B Q8 or 13B Q4 | 25–40 tok/s |
| 8 GB (RTX 3070, 4060) | 13B Q8 or 34B Q4 | 40–60 tok/s |
| 16 GB+ | 70B+ | 30–80 tok/s |

**Integrated / shared GPU** (AMD Radeon Vega 6/7, Intel Iris Xe) pulls VRAM from system RAM. Effective VRAM ≈ 0.5–2 GB — only good for CPU inference with llama.cpp.

---

## CPU Matters Too (But Less)

CPU matters for:
- Models too large to fit in VRAM (CPU offload layers)
- Prompt processing speed (prefill)
- Tokenizer and tool-call overhead

Good mobile CPUs for LLM (in order):
1. AMD Ryzen 5 5600U / 5700U — strong AVX2, good for CPU inference
2. Intel i5-8300H / i7-8750H — older but solid for GPU-paired setups
3. AMD Ryzen 5 4500U — 6 cores, 6 threads (no hyperthreading), acceptable
4. Intel i3-1215U / i5-1235U — weakest tier, fine if GPU carries load

---

## RAM

- **8 GB** — minimum; can run 7B in VRAM + OS
- **16 GB** — comfortable; can offload 13B layers to RAM
- **32 GB** — run large models mostly in RAM (slow but works)

DDR4 vs DDR5 matters little for GPU inference. Matters more for CPU-only inference (memory bandwidth).

---

## Storage

Models are large: 7B Q4 ≈ 4 GB, 13B Q4 ≈ 8 GB, 34B Q4 ≈ 20 GB.

- Extra SATA slot on a laptop = add a cheap 1–2 TB HDD/SSD for model storage
- Without it, 256 GB SSD fills up fast

---

## Comparison Workflow

When comparing laptops from listings (Avito, online stores):

1. **Filter immediately**: does it have a discrete GPU? If no → CPU-only tier, skip for LLM
2. **Identify GPU model**: GTX 1050 / 1050 Ti / 1650 / RTX 30xx / 40xx
3. **Check VRAM**: GTX 1050 = 4 GB, GTX 1050 Ti = 4 GB, RTX 3060 = 6 GB
4. **Check CPU generation**: 8th-gen Intel / Ryzen 5000 >> 7th-gen Intel / Ryzen 2000
5. **Note extras**: extra SATA slot (for model storage), RAM slots (for upgrade)

Use `delegate_task` with `toolsets: ["web"]` or `["browser"]` to scrape specs from listing pages in parallel.

---

## GPU Tier Reference (Mobile, Common Used Market)

| GPU | VRAM | CUDA Cores | LLM Rating |
|-----|------|-----------|------------|
| GTX 1050 | 4 GB | 640 | ✅ Entry |
| GTX 1050 Ti | 4 GB | 768 | ✅ Entry+ (~25% faster than 1050) |
| GTX 1060 | 6 GB | 1280 | ✅ Good |
| GTX 1650 | 4 GB | 1024 | ✅ Good (newer arch) |
| RTX 2060 | 6 GB | 1920 | ✅✅ Very good |
| RTX 3060 mobile | 6 GB | 3840 | ✅✅✅ Excellent |
| RTX 4060 mobile | 8 GB | 3072 | ✅✅✅ Excellent |

---

## Pitfalls

- **GTX 1050 2GB variant exists** — some cheaper listings have the 2 GB version. Always verify VRAM with seller.
- **"Shared memory" in Windows Task Manager** ≠ dedicated VRAM. Dedicated VRAM is what matters.
- **Laptop GPU ≠ Desktop GPU** — mobile GTX 1050 is ~30% slower than desktop GTX 1050. Still fine for 7B inference.
- **AMD integrated "Radeon RX Vega 6"** is integrated, NOT discrete — no dedicated VRAM.
- **exo / distributed inference** — if you have multiple machines on a LAN, exo can pool their GPUs. A cluster of two 4 GB VRAM machines can serve 13B+ models.

---

## References

- See `references/laptop-comparison-session.md` for a worked example comparing 7 laptops in the 30-36k RUB range (Lenovo K14, Xiaomi Mi, MSI Modern, HP Pavilion GTX 1050, Acer GTX 1050, Asus GTX 1050, Asus GTX 1050 Ti).
- **Session conclusion**: in the 30-36k RUB used market, HP Pavilion (i5-8300H + GTX 1050 4GB) and Asus (i5-7300HQ + GTX 1050 Ti 4GB) are the top picks. GTX 1050 Ti is ~25% faster; i5-8300H is a newer/better CPU than i5-7300HQ. Extra SATA slot (present on Acer and one Asus model) is valuable for model storage.
