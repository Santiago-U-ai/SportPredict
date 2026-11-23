# Dataset inicial

`laliga_2026_27.csv`: 128 partidos reales de Primera División española,
temporada 2026/27 (en curso), con resultados, tiros, córners y tarjetas.
No contiene encuentros futuros.

- Fuente: API pública de ESPN (`site.api.espn.com`, competición `esp.1`).
- Obtención: script `actualizar_datos.py` en la raíz del repositorio.
- Actualizado: 22 de noviembre de 2026.
- Nombres de equipos adaptados a los alias cortos del proyecto para conservar
  los escudos guardados en `frontend/assets/clubs/`.

Los datos iniciales se guardan en SQLite durante el primer arranque. Las
importaciones posteriores se guardan en SQLite, sin modificar este archivo.

Para renovar el dataset con los partidos jugados hasta hoy:

    python actualizar_datos.py --import-url http://127.0.0.1:8000

Los escudos en `frontend/assets/clubs/` proceden de los enlaces públicos de la API
de equipos de ESPN (https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/teams).
Se emplean para identificar a los equipos. Los emblemas pertenecen a sus respectivos
clubes; no implican asociación con SportPredict.
