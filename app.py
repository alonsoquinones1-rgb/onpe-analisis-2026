import os
import json
import logging
from flask import Flask, Response
from apscheduler.schedulers.background import BackgroundScheduler
import scraper

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")
_html_cache = {"content": "<p>Cargando datos...</p>", "ok": False}
_history = []

def _load_history():
    global _history
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                _history = json.load(f)
            log.info(f"Historial cargado: {len(_history)} snapshots")
    except Exception as e:
        log.warning(f"No se pudo cargar historial: {e}")
        _history = []

def _save_history():
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(_history[-500:], f)
    except Exception as e:
        log.warning(f"No se pudo guardar historial: {e}")

def refresh():
    global _history
    log.info("Actualizando datos ONPE...")
    try:
        data = scraper.fetch_data()
        if data:
            snap = {
                "ts":          data["timestamp"][:16].replace("T", " "),
                "pct":         data["nacional"]["actas_pct"],
                "lead":        data["analysis"]["lead"],
                "keiko_pct":   data["analysis"]["keiko_pct"],
                "sanchez_pct": data["analysis"]["sanchez_pct"],
                "ext_pct":     data["extranjero"]["actas_pct"],
                "ext_lead":    data["extranjero"]["keiko_votos"] - data["extranjero"]["sanchez_votos"],
            }
            # Solo agregar si el % procesado cambió (evita duplicados en reinicios)
            if not _history or _history[-1]["pct"] != snap["pct"]:
                _history.append(snap)
                _save_history()

            _html_cache["content"] = scraper.generar_html(data, _history)
            _html_cache["ok"] = True
            log.info(f"OK — Keiko {data['analysis']['keiko_pct']}% | Lead {data['analysis']['lead']:+,} | Snaps: {len(_history)}")
        else:
            log.warning("fetch_data() devolvió None")
    except Exception as e:
        log.error(f"Error al actualizar: {e}")

@app.route("/")
def index():
    return Response(_html_cache["content"], mimetype="text/html")

@app.route("/refresh")
def manual_refresh():
    refresh()
    return Response(_html_cache["content"], mimetype="text/html")

@app.route("/status")
def status():
    return {"ok": _html_cache["ok"], "cached": len(_html_cache["content"]) > 100, "snapshots": len(_history)}

if __name__ == "__main__":
    _load_history()
    refresh()

    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh, "interval", minutes=5, id="onpe_refresh")
    scheduler.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
