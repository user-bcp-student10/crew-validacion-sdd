"""Validación SDD por roles: Architect → Backend → Frontend → Testing → Security → Chapter.

Uso:
    python validar.py                                   # proyecto por defecto, con aprobación humana
    python validar.py --solo-evidencia                  # solo las verificaciones deterministas
    python validar.py --roles architect,testing         # solo algunos roles
    python validar.py --auto                            # aprueba cada informe sin preguntar
    python validar.py --repo ../otra/ruta --reiniciar   # otra copia del repo, ignorando el checkpoint
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

from sdd_crew import ejecutor, formato, llm  # noqa: E402
from sdd_crew.flujo import ejecutar_flujo  # noqa: E402
from sdd_crew.proyecto import Proyecto  # noqa: E402
from sdd_crew.roles import POR_CLAVE, ROLES  # noqa: E402
from sdd_crew.roles.base import Rol  # noqa: E402

LINEAS_VISTA_PREVIA = 40


def elegir_roles(texto: str | None) -> tuple[Rol, ...]:
    if not texto:
        return ROLES
    claves = [c.strip().lower() for c in texto.split(",") if c.strip()]
    desconocidas = [c for c in claves if c not in POR_CLAVE]
    if desconocidas:
        raise SystemExit(f"Roles desconocidos: {', '.join(desconocidas)}. Usa: {', '.join(POR_CLAVE)}")
    return tuple(r for r in ROLES if r.clave in claves)


def aprobar_en_consola(rol: Rol, informe: str, borrador: Path) -> tuple[str, str]:
    lineas = informe.strip().splitlines()
    print("\n" + "─" * 72)
    print(f"Informe de {rol.nombre} · {len(lineas)} líneas · completo en: {borrador}")
    print("─" * 72)
    print("\n".join(lineas[:LINEAS_VISTA_PREVIA]))
    if len(lineas) > LINEAS_VISTA_PREVIA:
        print(f"[... {len(lineas) - LINEAS_VISTA_PREVIA} líneas más en el archivo ...]")
    h = formato.hallazgos_por_severidad(informe)
    print("─" * 72)
    print(f"Veredicto: {formato.veredicto(informe) or 'sin veredicto'} · "
          f"Hallazgos: {h['ALTA']} alta, {h['MEDIA']} media, {h['BAJA']} baja")
    while True:
        opcion = input("¿Aprobar? [s] sí · [r] reintentar con feedback · [n] rechazar y detener: ").strip().lower()
        if opcion == "s":
            return "s", ""
        if opcion == "n":
            return "n", ""
        if opcion == "r":
            feedback = input("Feedback para el agente: ").strip()
            if feedback:
                return "r", feedback
            print("Escribe el feedback para reintentar.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validación SDD con agentes por rol (CrewAI).")
    p.add_argument("--proyecto", default=str(RAIZ / "proyectos" / "wallet-onboarding.yaml"),
                   help="YAML del proyecto a validar")
    p.add_argument("--repo", help="Ruta del repositorio a validar (reemplaza la del YAML)")
    p.add_argument("--roles", help="Roles separados por coma (por defecto, los seis)")
    p.add_argument("--salida", default=str(RAIZ / "output"), help="Carpeta de informes")
    p.add_argument("--auto", action="store_true", help="Aprobar cada informe sin preguntar")
    p.add_argument("--reiniciar", action="store_true", help="Ignorar el checkpoint")
    p.add_argument("--solo-evidencia", action="store_true", help="Solo verificaciones deterministas, sin agentes")
    args = p.parse_args(argv)

    try:
        proyecto = Proyecto.desde_yaml(args.proyecto, args.repo)
        roles = elegir_roles(args.roles)
        modelo = "ninguno" if args.solo_evidencia else llm.nombre_modelo()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Validación SDD · {proyecto.nombre}")
    print(f"Repo: {proyecto.repo} · Spec: {proyecto.spec} · {len(proyecto.ids_spec)} IDs")
    if not args.solo_evidencia:
        print(f"Modelo: {modelo} · Roles: {' → '.join(r.nombre for r in roles)}")

    aprobar = (lambda *_: ("s", "")) if args.auto else aprobar_en_consola
    resumen = ejecutar_flujo(proyecto, roles, ejecutor.ejecutar, aprobar, Path(args.salida), modelo,
                             reiniciar=args.reiniciar, solo_evidencia=args.solo_evidencia)

    print("\n" + "═" * 72)
    print(f"RESULTADO: {resumen['resultado']} — {resumen['motivo']}")
    print(f"Informes en {Path(args.salida).resolve()} (empieza por resumen.md)")
    if args.solo_evidencia:
        return 0 if resumen["evidencia_ok"] is not False else 1
    return 0 if resumen["resultado"] == "APROBADO" else 1


if __name__ == "__main__":
    sys.exit(main())
