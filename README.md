# Delfín Check-in · media auto

Pipeline **solo** de Delfín Check-in. Coste **0 €**. MacBook M1, 8 GB.

Cada día se genera **el mismo pack**:

1. Reel de **Lucía** (dolor de tiempo/legal)
2. Reel de **Pablo** (dolor de dinero)
3. **Carrusel de Lucía** (explica su vídeo)
4. **Carrusel de Pablo** (explica su vídeo)
5. **2 stories** (una frase + registro en la web)

Mismas piezas 9:16 para Instagram, Facebook, TikTok y YouTube Shorts/Stories.

[![Al hacer push](https://github.com/Arroyador69/delfincheckin-media-auto/actions/workflows/push.yml/badge.svg)](https://github.com/Arroyador69/delfincheckin-media-auto/actions/workflows/push.yml)

Repo: [Arroyador69/delfincheckin-media-auto](https://github.com/Arroyador69/delfincheckin-media-auto)

## Pack del día

```bash
source .venv/bin/activate
python -m delfin_media day
python -m delfin_media open
```

Cada Reel: hook (~3–5 s, persona preocupada **en movimiento**, subtítulos amarillos grandes) → cuerpo con la **app** (letterbox) → cierre idéntico (logo + delfincheckin.com).

El carrusel **no copia** el hook ni el locutado del Reel. Cada uno (tiempo vs dinero) tiene **título y textos propios**. 1080×1350 (IG/FB) y 1080×1920 (TikTok/YouTube).

Las stories **no** explican el vídeo. Recuerdan con una frase y mandan a `delfincheckin.com` (una propiedad gratis, sin tarjeta).

```bash
python -m delfin_media day --lucia-pain domingo_dnis --pablo-pain dinero_comision
python -m delfin_media clean   # borra output/ready para liberar espacio
```

## Dónde está el push (GitHub)

Los commits **no** aparecen en la pestaña Actions vacía. Aparecen aquí:

1. [Code](https://github.com/Arroyador69/delfincheckin-media-auto)
2. [Actions → Al hacer push](https://github.com/Arroyador69/delfincheckin-media-auto/actions/workflows/push.yml)

## Qué hace

| Pieza | Qué es |
| --- | --- |
| Reel | Hook en movimiento + app + cierre fijo |
| Carrusel | Un pack por vídeo, con el nombre de Lucía o Pablo |
| Stories | 2 al día, frase + CTA a la web |
| Voz | Azure Dragon HD (Ximena/Tristan, España). Clave en `.env`. |
| Guion | `spoken_hook` + cuerpo en `data/pains.yaml` |

Copia tus MP4 de la app a `assets/bank/app/`. Si faltan, el cuerpo usa una habitación.

## Instalar

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-voice.txt
# Copia .env.example a .env y pega AZURE_SPEECH_KEY + AZURE_SPEECH_REGION
python -m delfin_media doctor
python -m delfin_media bank
```

## Límites

- Solo Delfín Check-in. Precios en `data/product.yaml`.
- No Flux para personas. Banco en `assets/bank/`.
- Este M1 no corre LTX ni ComfyUI.
- Aún no publica solo: tú ves el MP4 y lo subes.

## Estructura

```
data/pains.yaml      dolores + guiones
data/stories.yaml    frases de stories
data/personas.yaml   Lucía / Pablo / …
assets/bank/hooks/   clips de estrés (mujer y hombre)
assets/bank/app/     tus MP4 de la app
output/ready/*_dia/  pack del día para subir
```
