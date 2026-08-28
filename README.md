# Delfín Check-in · media auto

Pipeline local para Reels y Shorts **solo** de Delfín Check-in: dolores de propietarios (domingos copiando DNIs, parte de viajeros, comisiones de Airbnb, lo que no se entiende del producto). No genera vídeos de otros temas.

Se prueba en este MacBook Pro M1 (8 GB). Cuando esté listo, se copia la carpeta al Mac Mini y se lanza en terminal. **En el Mini no hace falta Cursor** para crear vídeos: hace falta Python 3.11, ffmpeg y este repo. Cursor solo si quieres seguir tocando el código.

Repo: [Arroyador69/delfincheckin-media-auto](https://github.com/Arroyador69/delfincheckin-media-auto)

## Qué hace

1. Elige un dolor (domingo, MIR, dinero que se escapa…) y una persona IA.
2. Usa un guion cerrado de `data/pains.yaml` (hechos de `data/product.yaml`).
3. Voz española gratis (Edge TTS), más lenta y grave para que suene a locución, no a asistente.
4. Tres tomas del dolor (gráficos de marca teal/amarillo/logo, como Check-in Scan). Las caras IA de Flux salían asiáticas; se dejan en `visual_mode: faces` para más adelante.
5. Subtítulos amarillos sincronizados y tarjeta final con logo y [delfincheckin.com](https://delfincheckin.com).
6. Por cada Reel, un carrusel de 3 imágenes + caption para Instagram y Facebook (`output/ready/<slug>_ig/`). No TikTok ni YouTube.
7. Cada push a GitHub dispara Actions (`Push` → job `Check`).
8. Deja el MP4 en `output/ready/`. Tú lo ves y lo subes. Aún no publica solo.

Todo el pipeline es **gratis**: Edge TTS, Pollinations/Flux, FFmpeg local. Cero APIs de pago.

## Instalar (este Mac o el Mini)

```bash
cd "/ruta/a/delfincheckin-media-auto"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# ffmpeg: brew install ffmpeg   (ya está en este Mac)
python -m delfin_media doctor
```

## Crear vídeos

```bash
source .venv/bin/activate
python -m delfin_media list
python -m delfin_media generate
python -m delfin_media generate --count 3 --money
python -m delfin_media generate --pain domingo_dnis --persona lucia
python -m delfin_media open
```

`--money` fuerza ángulos de “pueden ganar más” (microsite, huésped repetidor, reseñas Google, tiempo = más reservas).

`--llm` intenta Ollama. En 8 GB no lo uses: se come la RAM. Los guiones de plantilla están escritos para boca, no hace falta.

## Pasar al Mac Mini

1. Copia esta carpeta (sin `.venv`).
2. En el Mini: `brew install python@3.11 ffmpeg` si faltan.
3. Repite el bloque de instalar.
4. Deja el Mini encendido y, cuando quieras, `python -m delfin_media generate --count 5`.
5. Cursor en el Mini es opcional.

Plantilla de arranque automático: `scripts/com.delfincheckin.media.plist.example`.

## Límites (a propósito)

- Solo Delfín Check-in. Cero temas genéricos tipo MoneyPrinterTurbo.
- Precios y normas salen de `data/product.yaml`. Si cambia un plan, se edita ahí.
- No se inventan importes de multa ni testimonios con nombre.
- Este M1 tiene 8 GB: no corre LTX ni vídeo IA local. El movimiento sale de 3 fotos + cámara (Ken Burns), todo gratis.

## Estructura

```
data/product.yaml    hechos y precios
data/pains.yaml      dolores + guiones
data/personas.yaml   anfitriones IA
delfin_media/        pipeline
output/ready/        MP4 para subir
```
