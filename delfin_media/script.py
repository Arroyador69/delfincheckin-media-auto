from __future__ import annotations

import random
import re
from dataclasses import dataclass

from delfin_media.config import Config, load_yaml
from delfin_media.paths import ROOT


@dataclass(frozen=True)
class Pain:
    id: str
    theme: str
    money_angle: bool
    hook: str
    spoken_hook: str
    scene: str
    image_extra: str
    scripts: list[str]


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    gender: str
    age: int
    city: str
    role: str
    voice: str
    seed: int
    image_prompt: str
    poses: tuple[str, ...]


@dataclass(frozen=True)
class Script:
    pain_id: str
    persona_id: str
    hook: str
    spoken_hook: str
    text: str
    source: str


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_pains() -> list[Pain]:
    raw = load_yaml("pains.yaml")["pains"]
    return [
        Pain(
            id=item["id"],
            theme=item["theme"],
            money_angle=bool(item["money_angle"]),
            hook=item["hook"],
            spoken_hook=_clean(item.get("spoken_hook") or item["hook"]),
            scene=item["scene"],
            image_extra=item["image_extra"],
            scripts=[_clean(s) for s in item["scripts"]],
        )
        for item in raw
    ]


def load_personas() -> list[Persona]:
    raw = load_yaml("personas.yaml")["personas"]
    return [
        Persona(
            id=item["id"],
            name=item["name"],
            gender=item["gender"],
            age=int(item["age"]),
            city=item["city"],
            role=item["role"],
            voice=item["voice"],
            seed=int(item["seed"]),
            image_prompt=_clean(item["image_prompt"]),
            poses=tuple(_clean(p) for p in item["poses"]),
        )
        for item in raw
    ]


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def validate_script(text: str, cfg: Config, spoken_hook: str = "") -> list[str]:
    errors: list[str] = []
    full = _clean(f"{spoken_hook} {text}")
    n = word_count(full)
    if n < cfg.min_words:
        errors.append(f"corto ({n} palabras)")
    if n > cfg.max_words:
        errors.append(f"largo ({n} palabras)")
    low = full.lower()
    if "delfín check-in" not in low and "delfincheckin.com" not in low:
        errors.append("no menciona Delfín Check-in ni la URL")
    product = load_yaml("product.yaml")
    for banned in product["must_not_say"]:
        if banned.lower() in low:
            errors.append(f"frase prohibida: {banned}")
    hook_n = word_count(spoken_hook) if spoken_hook else 0
    if spoken_hook and (hook_n < 5 or hook_n > 16):
        errors.append(f"hook de 3s ({hook_n} palabras, debe 5-16)")
    return errors


def pick_pain(pain_id: str | None = None, money_only: bool = False) -> Pain:
    pains = load_pains()
    if money_only:
        pains = [p for p in pains if p.money_angle] or pains
    if pain_id:
        for pain in pains:
            if pain.id == pain_id:
                return pain
        known = ", ".join(p.id for p in load_pains())
        raise SystemExit(f"Pain desconocido: {pain_id}. Usa: {known}")
    return random.choice(pains)


def pick_persona(persona_id: str | None = None) -> Persona:
    personas = load_personas()
    if persona_id:
        for persona in personas:
            if persona.id == persona_id:
                return persona
        known = ", ".join(p.id for p in personas)
        raise SystemExit(f"Persona desconocida: {persona_id}. Usa: {known}")
    return random.choice(personas)


def template_script(pain: Pain, persona: Persona, cfg: Config) -> Script:
    text = random.choice(pain.scripts)
    errors = validate_script(text, cfg, spoken_hook=pain.spoken_hook)
    if errors:
        raise RuntimeError(f"Plantilla inválida {pain.id}: {errors}")
    return Script(
        pain_id=pain.id,
        persona_id=persona.id,
        hook=pain.hook,
        spoken_hook=pain.spoken_hook,
        text=text,
        source="template",
    )


def llm_script(pain: Pain, persona: Persona, cfg: Config) -> Script | None:
    """Opcional. En 8 GB de RAM se omite salvo --llm."""
    prompt_path = ROOT / "prompts" / "script.md"
    system = prompt_path.read_text(encoding="utf-8")
    product = load_yaml("product.yaml")
    user = (
        f"Persona: {persona.name}, {persona.age} años, {persona.city}. {persona.role}\n"
        f"Dolor: {pain.hook}\nEscena: {pain.scene}\n"
        f"Hechos:\n{product}\n"
        "Devuelve SOLO el locutado, sin comillas ni título."
    )
    try:
        import json
        import urllib.request

        body = json.dumps(
            {
                "model": "mistral",
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
        text = _clean(payload.get("message", {}).get("content", ""))
        if not text:
            return None
        if validate_script(text, cfg, spoken_hook=pain.spoken_hook):
            return None
        return Script(
            pain_id=pain.id,
            persona_id=persona.id,
            hook=pain.hook,
            spoken_hook=pain.spoken_hook,
            text=text,
            source="ollama",
        )
    except Exception:
        return None


def build_script(
    cfg: Config,
    pain_id: str | None = None,
    persona_id: str | None = None,
    money_only: bool = False,
    use_llm: bool = False,
) -> tuple[Pain, Persona, Script]:
    pain = pick_pain(pain_id, money_only=money_only)
    persona = pick_persona(persona_id)
    script = llm_script(pain, persona, cfg) if use_llm else None
    if script is None:
        script = template_script(pain, persona, cfg)
    return pain, persona, script
