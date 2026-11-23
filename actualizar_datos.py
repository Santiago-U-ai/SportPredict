# -*- coding: utf-8 -*-
"""Actualiza el dataset de SportPredict con la temporada de La Liga en curso.

Fuente: API pública de ESPN (la misma que ya usa el proyecto para los escudos).
Genera data/laliga_<temporada>.csv y, opcionalmente, lo importa en la app.

Uso:
    python actualizar_datos.py
    python actualizar_datos.py --import-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd

from sportpredict import model

ROOT = Path(__file__).parent
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1"
HEADERS = {"User-Agent": "SportPredict/1.0 (+https://github.com/dokiromboide/SportPredict)"}

# Nombres cortos que ya usa el proyecto, para conservar escudos y el partido destacado.
ALIASES = {
    "Alavés": "Alaves",
    "Athletic Club": "Ath Bilbao",
    "Atlético Madrid": "Ath Madrid",
    "Celta Vigo": "Celta",
    "Espanyol": "Espanol",
    "Rayo Vallecano": "Vallecano",
    "Real Betis": "Betis",
    "Real Sociedad": "Sociedad",
    "Racing Santander": "Racing",
    "Málaga": "Malaga",
}


def fetch(url: str, tries: int = 3):
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(1 + attempt)


def months(season_start: int):
    """Meses de la temporada, desde agosto hasta el mes actual."""
    today = date.today()
    year, month = season_start, 8
    result = []
    while (year, month) <= (today.year, today.month):
        result.append(f"{year}{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return result


def number(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return ""


def match_stats(event_id, team_ids):
    data = fetch(f"{BASE}/summary?event={event_id}")
    by_id = {}
    for team in data.get("boxscore", {}).get("teams", []):
        values = {x.get("name"): x.get("displayValue") for x in team.get("statistics", [])}
        by_id[team["team"]["id"]] = values
    stats = {}
    for side, team_id in team_ids.items():
        values = by_id.get(team_id, {})
        stats[side] = {key: number(values.get(key))
                       for key in ("wonCorners", "yellowCards", "totalShots", "shotsOnTarget")}
    return stats


def build_row(event):
    competition = event["competitions"][0]
    home = next(c for c in competition["competitors"] if c["homeAway"] == "home")
    away = next(c for c in competition["competitors"] if c["homeAway"] == "away")
    if home.get("score") is None or away.get("score") is None:
        return None
    stats = match_stats(event["id"], {"home": home["team"]["id"], "away": away["team"]["id"]})
    name = lambda team: ALIASES.get(team["team"]["displayName"], team["team"]["displayName"])
    return {
        "Date": event["date"][:10],
        "HomeTeam": name(home),
        "AwayTeam": name(away),
        "FTHG": int(float(home["score"])),
        "FTAG": int(float(away["score"])),
        "HC": stats["home"]["wonCorners"], "AC": stats["away"]["wonCorners"],
        "HY": stats["home"]["yellowCards"], "AY": stats["away"]["yellowCards"],
        "HS": stats["home"]["totalShots"], "AS": stats["away"]["totalShots"],
        "HST": stats["home"]["shotsOnTarget"], "AST": stats["away"]["shotsOnTarget"],
    }


def main():
    today = date.today()
    season_start = today.year if today.month >= 7 else today.year - 1
    season = f"{season_start}/{str(season_start + 1)[-2:]}"
    parser = argparse.ArgumentParser(description="Actualiza el dataset de La Liga desde ESPN.")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "data" / f"laliga_{season_start}_{str(season_start + 1)[-2:]}.csv")
    parser.add_argument("--import-url", help="Servidor SportPredict para importar el CSV (ej. http://127.0.0.1:8000).")
    args = parser.parse_args()

    events = {}
    for month in months(season_start):
        data = fetch(f"{BASE}/scoreboard?dates={month}&limit=1000")
        for event in data.get("events", []):
            if event["status"]["type"].get("completed") and event["date"][:10] <= today.isoformat():
                events[event["id"]] = event
    if not events:
        raise SystemExit("ESPN no devolvió partidos completados para la temporada en curso.")

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = [row for row in pool.map(build_row, events.values()) if row]

    frame = (pd.DataFrame(rows)
             .drop_duplicates(["Date", "HomeTeam", "AwayTeam"], keep="last")
             .sort_values(["Date", "HomeTeam", "AwayTeam"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False)

    # Autocomprobación con el mismo validador de la aplicación.
    clean = model.load_csv(args.out.read_bytes())
    metrics = model.evaluate(clean)
    assert len(clean) >= 30, "Se necesitan al menos 30 partidos."
    print(f"Temporada {season}: {len(clean)} partidos, "
          f"{len(set(clean.HomeTeam) | set(clean.AwayTeam))} equipos, "
          f"{clean.Date.min().date()} a {clean.Date.max().date()}")
    print(f"Exactitud {metrics['accuracy']:.1%} | referencia {metrics['baseline']:.1%} | "
          f"log loss {metrics['log_loss']:.3f} | prueba {metrics['test_count']} partidos")
    print(f"Guardado en {args.out}")

    if args.import_url:
        url = args.import_url.rstrip("/") + "/api/dataset?name=" + urllib.parse.quote(args.out.name)
        request = urllib.request.Request(
            url, data=args.out.read_bytes(), method="POST",
            headers={**HEADERS, "Content-Type": "text/csv"})
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        print(f"Importado en la app: {result['matches']} partidos, "
              f"datos hasta {result['to']}")


if __name__ == "__main__":
    main()
