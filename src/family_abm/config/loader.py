"""Chargement, surcharge, validation et empreinte de la configuration (03, 10 §1).

Séquence : lecture des YAML → arbre brut unique (clés de ``simulation.yaml`` à la racine,
un espace de noms par fichier) → surcharges par chemin pointé, couche par couche dans l'ordre
normatif de 03 §14 → validation Pydantic de l'arbre complet. Toute erreur devient une
``ConfigError`` qui nomme le chemin pointé fautif.
"""

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from family_abm.config.schemas import (
    ParametersRegistry,
    Provenance,
    SimulationConfig,
)
from family_abm.core.errors import ConfigError
from family_abm.core.types import ConfigHash

SIMULATION_FILE = "simulation.yaml"
NAMESPACE_FILES: Mapping[str, str] = {
    "profiles": "cognitive_profiles.yaml",
    "household_rules": "household_rules.yaml",
    "needs": "needs.yaml",
    "economic_params": "economic_params.yaml",
}
"""Espaces de noms chargés par la V1 (03 §1). ``plans``, ``affect``, ``risk``,
``population`` et ``patterns`` sont ajoutés par les tickets qui les introduisent."""

RESERVED_NAMESPACES = frozenset(
    {*NAMESPACE_FILES, "plans", "affect", "risk", "population", "patterns"}
)
REGISTRY_FILE = "parameters_registry.yaml"
GATES_FILE = Path("docs") / "GATES.md"
GATE_V1_PASSED = re.compile(r"^\s*gate_v1:\s*passed\s*$", re.MULTILINE)
HASH_EXCLUDED_ROOT_KEYS = frozenset({"seed"})
"""Hors empreinte : un run est identifié par le couple (config_hash, seed) (50 §1, 60)."""
HASH_EXCLUDED_METADATA = frozenset({"provenance", "source", "provenance_by_path"})
"""Métadonnées sans effet sur la trajectoire, hors empreinte (``data.source`` reste dedans)."""

type Overrides = Mapping[str, Any]


# --- lecture


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"fichier de configuration absent : {path}")
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} : YAML illisible — {exc}") from exc
    if not isinstance(content, dict):
        raise ConfigError(f"{path.name} : le contenu doit être un dictionnaire")
    return content


def _read_profiles(path: Path) -> dict[str, Any]:
    """Lit ``cognitive_profiles.yaml`` ; sa provenance de fichier s'applique à chaque profil
    qui n'en déclare pas (03 §3 : ``provenance`` au niveau du fichier)."""
    content = _read_yaml(path)
    profiles = content.pop("profiles", None)
    if not isinstance(profiles, dict):
        raise ConfigError(f"{path.name} : clé racine 'profiles' absente ou invalide")
    defaults = {key: content.pop(key) for key in ("provenance", "source") if key in content}
    if content:
        raise ConfigError(f"{path.name} : clés racine inconnues {sorted(content)}")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ConfigError(f"{path.name} : profil {name!r} invalide")
        for key, value in defaults.items():
            profile.setdefault(key, value)
    return profiles


def read_raw_config(config_dir: Path) -> dict[str, Any]:
    """Arbre brut, non validé, de la configuration de base."""
    tree = _read_yaml(config_dir / SIMULATION_FILE)
    clashes = RESERVED_NAMESPACES & tree.keys()
    if clashes:
        raise ConfigError(
            f"{SIMULATION_FILE} : clé racine portant le nom d'un autre fichier interdite "
            f"{sorted(clashes)} (03 §1, B1)"
        )
    for namespace, filename in NAMESPACE_FILES.items():
        path = config_dir / filename
        tree[namespace] = _read_profiles(path) if namespace == "profiles" else _read_yaml(path)
    return tree


# --- chemins pointés


def _expand(segment: str, node: Any, path: str, *, lenient: bool) -> list[Any]:
    """Clés désignées par un segment : ``*``, ``{a,b}``, indice de liste ou clé simple.

    ``lenient`` (sous un joker) : une branche qui ne porte pas le segment est ignorée
    au lieu d'être refusée.
    """

    def refuse(reason: str) -> list[Any]:
        if lenient:
            return []
        raise ConfigError(f"chemin {path!r} : {reason}")

    if isinstance(node, list):
        if segment == "*":
            return list(range(len(node)))
        if segment.isdigit() and int(segment) < len(node):
            return [int(segment)]
        return refuse(f"indice {segment!r} invalide")
    if not isinstance(node, dict):
        return refuse(f"{segment!r} sous une valeur non composée")
    if segment == "*":
        return list(node)
    if segment.startswith("{") and segment.endswith("}"):
        keys = [key.strip() for key in segment[1:-1].split(",")]
        missing = [key for key in keys if key not in node]
        if missing and not lenient:
            raise ConfigError(f"chemin {path!r} : clés inconnues {missing}")
        return [key for key in keys if key in node]
    return [segment]


def _targets(tree: dict[str, Any], path: str) -> Iterator[tuple[Any, Any]]:
    """Couples (conteneur, clé) désignés par ``path``. Sous un joker, les branches qui ne
    portent pas la suite du chemin sont ignorées ; ailleurs, un segment inconnu est refusé.
    Une feuille absente hors joker est rendue : le schéma jugera la clé nouvelle."""
    segments = path.split(".")
    frontier: list[tuple[Any, bool]] = [(tree, False)]
    for depth, segment in enumerate(segments):
        last = depth == len(segments) - 1
        wildcard = segment == "*" or segment.startswith("{")
        next_frontier: list[tuple[Any, bool]] = []
        for node, lenient in frontier:
            for key in _expand(segment, node, path, lenient=lenient):
                exists = _has(node, key)
                if last:
                    if exists or not (wildcard or lenient):
                        yield node, key
                    continue
                if not exists:
                    if lenient:
                        continue
                    raise ConfigError(f"chemin {path!r} : segment inconnu {key!r}")
                next_frontier.append((node[key], lenient or wildcard))
        frontier = next_frontier


def apply_overrides(tree: dict[str, Any], overrides: Overrides) -> dict[str, Any]:
    """Copie de ``tree`` où chaque chemin pointé reçoit sa valeur (valeur absolue, 03 §11).

    ``*`` désigne toutes les clés d'un niveau, ``{a,b}`` une sélection explicite. Le parent
    d'une feuille doit exister ; une feuille nouvelle est ensuite jugée par le schéma.
    """
    result = copy.deepcopy(tree)
    for path, value in overrides.items():
        if path.split(".")[0] not in result:
            raise ConfigError(f"chemin {path!r} : espace de noms inconnu ou non chargé")
        targets = list(_targets(result, path))
        if not targets:
            raise ConfigError(f"chemin {path!r} : ne désigne aucun paramètre")
        for container, key in targets:
            container[key] = copy.deepcopy(value)
    return result


def resolve_path(tree: Mapping[str, Any], path: str) -> list[Any]:
    """Valeurs existantes désignées par ``path`` (jokers acceptés) ; liste vide si aucune.

    Lève ``ConfigError`` si un segment hors joker est inconnu."""
    return [node[key] for node, key in _targets(dict(tree), path) if _has(node, key)]


def _has(node: Any, key: Any) -> bool:
    return isinstance(node, list) or key in node


# --- validation


def _format_validation_error(error: ValidationError) -> str:
    lines = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "<racine>"
        message = item["msg"].removeprefix("Value error, ")
        value = item.get("input")
        shown = "" if isinstance(value, dict | list) else f" (valeur : {value!r})"
        lines.append(f"  - {location} : {message}{shown}")
    return "configuration invalide :\n" + "\n".join(lines)


def _check_provenance_paths(config: SimulationConfig) -> None:
    """Chaque chemin de ``provenance_by_path`` désigne un paramètre existant (J3)."""
    tree = config.economic_params.model_dump(mode="json", by_alias=True)
    for path in config.economic_params.provenance_by_path:
        try:
            found = resolve_path(tree, path)
        except ConfigError as exc:
            raise ConfigError(f"economic_params.provenance_by_path : {exc}") from exc
        if len(found) != 1 or isinstance(found[0], dict):
            raise ConfigError(
                f"economic_params.provenance_by_path : {path!r} doit désigner une valeur unique "
                "(scalaire ou table), sans joker"
            )


def _check_sampling_gate(config: SimulationConfig, gates_path: Path) -> None:
    """``invariant_run_sample_rate < 1`` exige la porte V1 verte (10 §12)."""
    if config.checks.invariant_run_sample_rate >= 1:
        return
    text = gates_path.read_text(encoding="utf-8") if gates_path.is_file() else ""
    if not GATE_V1_PASSED.search(text):
        raise ConfigError(
            "checks.invariant_run_sample_rate < 1 refusé : la porte V1 n'est pas déclarée "
            f"verte ('gate_v1: passed' absent de {gates_path})"
        )


def load_config(
    config_dir: Path | str = "config",
    overrides: Overrides | Iterable[Overrides] = (),
    *,
    gates_path: Path | None = None,
) -> SimulationConfig:
    """Charge, surcharge et valide la configuration.

    ``overrides`` est une couche de surcharges ou une suite de couches appliquées dans
    l'ordre (base → scénario → ``fixed`` → calibration → facteurs, 03 §14).
    """
    config_dir = Path(config_dir)
    layers = [overrides] if isinstance(overrides, Mapping) else list(overrides)
    for layer in layers:
        if not isinstance(layer, Mapping) or not all(isinstance(k, str) for k in layer):
            raise ConfigError(f"couche de surcharges invalide (dict chemin → valeur) : {layer!r}")
    tree = read_raw_config(config_dir)
    for layer in layers:
        tree = apply_overrides(tree, layer)
    try:
        # Validation stricte via JSON : refuse true → 1 ou "7" → 7, accepte les énumérations.
        config = SimulationConfig.model_validate_json(json.dumps(tree), strict=True)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from exc
    _check_provenance_paths(config)
    _check_sampling_gate(config, gates_path or config_dir.parent / GATES_FILE)
    return config


def load_registry(config_dir: Path | str, config: SimulationConfig) -> ParametersRegistry:
    """Charge le registre des paramètres (03 §12) ; chaque chemin d'un espace de noms chargé
    doit désigner au moins un paramètre de ``config``."""
    config_dir = Path(config_dir)
    try:
        registry = ParametersRegistry.model_validate_json(
            json.dumps(_read_yaml(config_dir / REGISTRY_FILE)), strict=True
        )
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from exc
    tree = config.model_dump(mode="json", by_alias=True)
    for spec in registry.parameters:
        namespace = spec.path.split(".")[0]
        if namespace not in RESERVED_NAMESPACES:
            raise ConfigError(f"{REGISTRY_FILE} : espace de noms inconnu dans {spec.path!r}")
        if namespace not in tree:
            continue  # espace de noms d'une version ultérieure, non chargé
        try:
            found = resolve_path(tree, spec.path)
        except ConfigError as exc:
            raise ConfigError(f"{REGISTRY_FILE} : {exc}") from exc
        if not found:
            raise ConfigError(f"{REGISTRY_FILE} : {spec.path!r} ne désigne aucun paramètre")
    return registry


# --- empreinte et provenance


def _strip_metadata(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: _strip_metadata(value)
            for key, value in node.items()
            if key not in HASH_EXCLUDED_METADATA
        }
    if isinstance(node, list):
        return [_strip_metadata(value) for value in node]
    return node


def canonical_json(config: SimulationConfig) -> str:
    """JSON canonique de la configuration résolue : seed, ``output.dir``, ``provenance`` et
    ``source`` exclus — l'empreinte identifie le modèle simulé, pas son étiquetage ni le
    répertoire de sortie. ``data.source`` est un paramètre et reste dans l'empreinte."""
    data = config.model_dump(
        mode="json",
        by_alias=True,
        exclude={**dict.fromkeys(HASH_EXCLUDED_ROOT_KEYS, True), "output": {"dir"}},
    )
    data_settings = data.pop("data")
    stripped = _strip_metadata(data) | {"data": data_settings}
    return json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def config_hash(config: SimulationConfig) -> ConfigHash:
    """``ConfigHash`` = SHA-256 du JSON canonique de la configuration résolue (03 §1)."""
    return hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()


def _provenances(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        if "provenance" in node:
            yield node["provenance"]
        for value in node.values():
            yield from _provenances(value)
    elif isinstance(node, list):
        for value in node:
            yield from _provenances(value)


def is_illustrative(config: SimulationConfig) -> bool:
    """Vrai si au moins un bloc porte ``provenance: PLACEHOLDER`` (03, 04 ``illustrative``)."""
    tree = config.model_dump(mode="json")
    return Provenance.PLACEHOLDER.value in set(_provenances(tree))
