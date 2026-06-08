import os
import logging
from flask import Flask, Response
from apscheduler.schedulers.background import BackgroundScheduler
import scraper

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)

_html_cache = {"content": "<p>Cargando datos...</p>", "ok": False}

def refresh():
    log.info("Actualizando datos ONPE...")
    try:
        data = scraper.fetch_data()
        if data:
            _html_cache["content"] = scraper.generar_html(data)
            _html_cache["ok"] = True
            log.info(f"OK — Keiko {data['analysis']['keiko_pct']}% | Lead {data['analysis']['lead']:+,}")
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
    return {"ok": _html_cache["ok"], "cached": len(_html_cache["content"]) > 100}

if __name__ == "__main__":
    # Fetch immediately on startup
    refresh()

    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh, "interval", minutes=20, id="onpe_refresh")
    scheduler.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
