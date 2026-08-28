# Delfín Check-in · media auto

Pipeline **solo** de Delfín Check-in: Reels 9:16 y posts de Instagram/Facebook sobre dolores de propietarios (domingos copiando DNIs, parte de viajeros al MIR, comisiones de Airbnb). Coste **0 €**. No TikTok ni YouTube.

[![Al hacer push](https://github.com/Arroyador69/delfincheckin-media-auto/actions/workflows/push.yml/badge.svg)](https://github.com/Arroyador69/delfincheckin-media-auto/actions/workflows/push.yml)

Repo: [Arroyador69/delfincheckin-media-auto](https://github.com/Arroyador69/delfincheckin-media-auto)

## Dónde está el push (GitHub)

Los commits **no** aparecen en la pestaña Actions. Aparecen aquí:

1. [Code](https://github.com/Arroyador69/delfincheckin-media-auto) — historial de archivos y commits.
2. [Actions → Al hacer push](https://github.com/Arroyador69/delfincheckin-media-auto/actions/workflows/push.yml) — el CI (doctor). Si ves “Get started with GitHub Actions”, estás en la pantalla vacía del repo, no en las ejecuciones. Entra en el workflow **Al hacer push**.

## Qué hace (personalizado, no MoneyPrinterTurbo genérico)

MoneyPrinterTurbo es útil como idea (stock gratis + voz + subtítulos), no como producto: busca clips al azar y no habla de Delfín Check-in. En este Mac (M1, 8 GB) **no cabe** vídeo IA local (LTX, ComfyUI, Flux de personas). Flux por Pollinations sacaba caras asiáticas. Por eso el material es un **banco curado**:

| Pieza | Qué es | Qué no es |
| --- | --- | --- |
| Post IG/FB | Foto fija de habitación/apartamento + texto, logo y colores | No se convierte en vídeo |
| Reel | 3 tomas (persona europea + 2 habitaciones) con Ken Burns, voz, **subtítulos amarillos**, endcard | No caras IA, no stock genérico de otros temas |
| Voz | Edge TTS (Elvira / Álvaro), gratis | — |
| Guion | Dolores de `data/pains.yaml` + hechos de `data/product.yaml` | No se inventan multas ni testimonios |

Fotos: Pexels (licencia comercial, 0 €). Hoteles y apartamentos que no son de España. Personas de aspecto europeo/mediterráneo, no Flux.

## Instalar

```bash
cd "/ruta/a/delfincheckin-media-auto"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m delfin_media doctor
python -m delfin_media bank
```

## Crear

```bash
source .venv/bin/activate
python -m delfin_media list
python -m delfin_media generate --pain domingo_dnis --persona lucia
python -m delfin_media generate --pain dinero_comision --persona pablo
python -m delfin_media open
```

Cada Reel deja:

- `output/ready/<slug>.mp4` — para Instagram Reels / Facebook
- `output/ready/<slug>_ig/` — 3 JPG 1080×1350 (fotos, no vídeos) + caption

`--money` fuerza ángulos de “pueden ganar más”. `--llm` intenta Ollama: en 8 GB no lo uses.

## Límites (a propósito)

- Solo Delfín Check-in.
- Precios y normas en `data/product.yaml`.
- No Flux para personas. Banco en `assets/bank/` + `data/bank.yaml`.
- Este M1 no corre LTX ni ComfyUI. El movimiento es Ken Burns sobre fotos.
- Aún no publica solo: tú ves el MP4 y lo subes.

## Estructura

```
data/product.yaml    hechos y precios
data/pains.yaml      dolores + guiones
data/personas.yaml   anfitriones (voz / ciudad)
data/bank.yaml       ids Pexels del banco
assets/bank/rooms/   habitaciones y apartamentos
assets/bank/people/  personas de aspecto europeo
assets/brand/        logo
delfin_media/        pipeline
output/ready/        MP4 y posts para subir
```
