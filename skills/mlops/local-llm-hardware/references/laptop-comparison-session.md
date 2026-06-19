# Laptop Comparison — Local LLM, ~30–37k RUB Budget

**Date:** May 2026  
**Goal:** Find best laptop for local LLM inference in budget ~30–37k RUB (б/у market)

## Candidates Evaluated

| # | Model | CPU | GPU | VRAM | RAM | Storage | Price | Source |
|---|-------|-----|-----|------|-----|---------|-------|--------|
| 1 | Lenovo K14 Gen 1 | Ryzen 5 5600U (6c/12t, 4.2GHz) | AMD Radeon (integrated) | ~0.5 GB shared | 8 GB DDR4 | 256 SSD | 29 990 ₽ | probookrf.ru (б/у) |
| 2 | Xiaomi Mi Notebook Pro 15.6 2021 | Ryzen 5 4500U (6c/6t) | AMD Radeon RX Vega 6 (integrated) | ~0.5 GB shared | 8 GB | 256 SSD | 36 990 ₽ | probookrf.ru (б/у) |
| 3 | MSI Modern 14 C12M | Intel i3-1215U | Intel Iris Xe | ~1 GB shared | 8 GB | 256 SSD | 34 900 ₽ | новый |
| 4 | HP Pavilion Gaming | Intel i5-8300H (4c/8t, 4.0GHz) | **GTX 1050 4 GB GDDR5** | **4 GB** | 8 GB | 256 SSD | 34 000 ₽ | Avito (б/у, отличное) |
| 5 | Acer (модель не уточнена) | Intel i5-7300HQ | **GTX 1050 4 GB** | **4 GB** | 8 GB | 128 SSD + доп. слот SATA | 34 000 ₽ | Avito |
| 6 | Asus (модель не уточнена) | Ryzen 5 2500U | **GTX 1050 4 GB** | **4 GB** | 8 GB | 128 SSD + 256 SSD | 35 000 ₽ | Avito |
| 7 | Asus (модель не уточнена) | Intel i5-7300HQ | **GTX 1050 Ti 4 GB** | **4 GB** | 8 GB | 128 SSD + доп. слот SATA | 35 000 ₽ | Avito |

## Ranking (LLM inference)

1. 🥇 **Asus GTX 1050 Ti** — лучший GPU (+25% к 1050), доп. слот под модели
2. 🥈 **HP Pavilion** — лучший CPU (i5-8300H, 2018), 4 GB VRAM, дешевле всех с GPU
3. 🥉 **Acer GTX 1050** — тот же GPU что HP, CPU слабее, но доп. слот SATA полезен
4. **Asus Ryzen 2500U + GTX 1050** — слабый CPU, зато два SSD
5–7. Lenovo/Xiaomi/MSI — только CPU inference, отпадают

## Key Insight

Наличие дискретного GPU (GTX 1050) даёт 10x+ прирост скорости инференса по сравнению с интегрированной графикой. При одинаковом бюджете — приоритет GPU над CPU поколением.

## Проверка VRAM

GTX 1050 существует в двух вариантах: 2 GB и 4 GB. Всегда уточнять у продавца перед покупкой.
