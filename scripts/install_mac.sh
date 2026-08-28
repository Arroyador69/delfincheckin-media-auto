# Copiar al Mac Mini y ejecutar una vez.

set -euo pipefail
brew install python@3.11 ffmpeg
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m delfin_media doctor
