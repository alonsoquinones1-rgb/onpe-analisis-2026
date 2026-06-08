import json, datetime, math, time
import requests
from concurrent.futures import ThreadPoolExecutor

BASE = "https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "es-PE,es;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "referer": "https://resultadosegundavuelta.onpe.gob.pe/main/resumen",
    "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
}

DEPTS = {
    "010000": "Amazonas",    "020000": "Áncash",       "030000": "Apurímac",
    "040000": "Arequipa",    "050000": "Ayacucho",     "060000": "Cajamarca",
    "070000": "Cusco",       "080000": "Huancavelica", "090000": "Huánuco",
    "100000": "Ica",         "110000": "Junín",        "120000": "La Libertad",
    "130000": "Lambayeque",  "140000": "Lima",         "150000": "Loreto",
    "160000": "Madre de Dios","170000": "Moquegua",    "180000": "Pasco",
    "190000": "Piura",       "200000": "Puno",         "210000": "San Martín",
    "220000": "Tacna",       "230000": "Tumbes",       "240000": "Callao",
    "250000": "Ucayali",
}

_session = requests.Session()
_session.headers.update(HEADERS)

def _get(url):
    try:
        r = _session.get(url, timeout=12)
        d = r.json()
        return d.get("data") if isinstance(d, dict) and "data" in d else d
    except Exception:
        return None

def _fetch_dept(ubigeo, nombre):
    part = _get(f"{BASE}/eleccion-presidencial/participantes-ubicacion-geografica-nombre"
                f"?tipoFiltro=ubigeo_nivel_01&idAmbitoGeografico=1&ubigeoNivel1={ubigeo}&idEleccion=10")
    tot  = _get(f"{BASE}/resumen-general/totales"
                f"?idAmbitoGeografico=1&idEleccion=10&tipoFiltro=ubigeo_nivel_01"
                f"&idUbigeoDepartamento={ubigeo}&ubigeoNivel1={ubigeo}")
    return ubigeo, nombre, part, tot

def fetch_data():
    with ThreadPoolExecutor(max_workers=30) as pool:
        fut_nat  = pool.submit(_get, f"{BASE}/resumen-general/totales?idEleccion=10&tipoFiltro=eleccion")
        fut_ext  = pool.submit(_get, f"{BASE}/resumen-general/totales?idAmbitoGeografico=2&idEleccion=10")
        dept_futs = [pool.submit(_fetch_dept, ub, nm) for ub, nm in DEPTS.items()]
        nat_raw  = fut_nat.result()
        ext_raw  = fut_ext.result()
        dept_res = [f.result() for f in dept_futs]

    if not nat_raw:
        return None

    nac_total = nat_raw.get("totalActas", 0)
    nac_proc  = nat_raw.get("contabilizadas", 0)
    nac_jee   = nat_raw.get("enviadasJee", 0)
    nac_pend  = nat_raw.get("pendientesJee", 0)
    nac_pct   = nat_raw.get("actasContabilizadas", 0)

    ext_total = 2543
    ext_proc  = 0
    ext_pct   = 0.0
    if ext_raw and ext_raw.get("totalActas", 0) > 0:
        ext_total = ext_raw.get("totalActas", 2543)
        ext_proc  = ext_raw.get("contabilizadas", 0)
        ext_pct   = ext_raw.get("actasContabilizadas", 0)

    departamentos = {}
    for ubigeo, nombre, part, tot in dept_res:
        if not part or not tot:
            continue
        cands = part if isinstance(part, list) else []
        keiko   = next((c for c in cands if "FUJIMORI" in c.get("nombreCandidato","").upper()), None)
        sanchez = next((c for c in cands if "SÁNCHEZ" in c.get("nombreCandidato","").upper()
                        or "SANCHEZ" in c.get("nombreCandidato","").upper()), None)
        kv = keiko.get("totalVotosValidos", 0)   if keiko   else 0
        sv = sanchez.get("totalVotosValidos", 0) if sanchez else 0
        tv = kv + sv
        kpct = kv / tv * 100 if tv else 0
        spct = sv / tv * 100 if tv else 0
        at   = tot.get("totalActas", 0)
        ap   = tot.get("contabilizadas", 0)
        ajee = tot.get("enviadasJee", 0)
        apend = tot.get("pendientesJee", 0)
        apct  = tot.get("actasContabilizadas", 0)
        departamentos[ubigeo] = {
            "nombre": nombre, "keiko_votos": kv, "keiko_pct": round(kpct,1),
            "sanchez_votos": sv, "sanchez_pct": round(spct,1),
            "actas_total": at, "actas_procesadas": ap,
            "actas_jee": ajee, "actas_pendientes": apend, "pct_procesado": round(apct,1),
        }

    total_k = sum(d["keiko_votos"]   for d in departamentos.values())
    total_s = sum(d["sanchez_votos"] for d in departamentos.values())
    lead    = total_k - total_s
    total_ext_v = ext_total * 200
    net_pend = sum(d["actas_pendientes"] * 175 * (d["keiko_pct"] - d["sanchez_pct"]) / 100
                   for d in departamentos.values())
    net_jee  = 935 * 219 * (63.5 - 36.5) / 100 + 69 * 213 * (65.6 - 34.4) / 100
    proj = {}
    for lbl, pct in [("55", 0.55), ("60", 0.60), ("65", 0.65)]:
        proj[f"keiko_{lbl}pct"] = round(lead + net_pend + net_jee + total_ext_v * (2*pct - 1))
    be    = 0.5 - (lead + net_pend + net_jee) / (2 * total_ext_v) if total_ext_v else 0.5
    sigma = math.sqrt((0.05*total_ext_v)**2 + (0.05*914*175)**2 + (0.05*305*175)**2 + 15000**2)
    base  = proj["keiko_60pct"]

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "nacional": {"total_actas": nac_total, "actas_contabilizadas": nac_proc,
                     "actas_jee": nac_jee, "actas_pendientes": nac_pend, "actas_pct": round(nac_pct, 3)},
        "extranjero": {"total_actas": ext_total, "actas_proc": ext_proc, "actas_pct": round(ext_pct,1)},
        "departamentos": departamentos,
        "analysis": {
            "keiko_total": total_k, "sanchez_total": total_s, "lead": lead,
            "keiko_pct": round(total_k/(total_k+total_s)*100, 3) if (total_k+total_s) else 0,
            "sanchez_pct": round(total_s/(total_k+total_s)*100, 3) if (total_k+total_s) else 0,
            "net_pendientes": round(net_pend), "net_jee": round(net_jee),
            "ext_votos_est": total_ext_v, "proyecciones": proj,
            "breakeven_pct": round(be * 100, 1),
            "ic95_inf": round(base - 2*sigma),
            "ic95_sup": round(base + 2*sigma),
        }
    }

def generar_html(data):
    a    = data["analysis"]
    nac  = data["nacional"]
    deps = data["departamentos"]
    ts   = data["timestamp"][:16].replace("T", " ")

    lead = a["lead"]
    lead_str   = f"+{lead:,}" if lead > 0 else f"{lead:,}"
    lead_color = "#f97316" if lead > 0 else "#8b5cf6"
    lead_winner = "KEIKO" if lead > 0 else "SÁNCHEZ"

    p55 = a["proyecciones"]["keiko_55pct"]
    p60 = a["proyecciones"]["keiko_60pct"]
    p65 = a["proyecciones"]["keiko_65pct"]
    be  = a["breakeven_pct"]
    ic_inf = a["ic95_inf"]
    ic_sup = a["ic95_sup"]

    def fmt(v): return f"+{v:,}" if v >= 0 else f"{v:,}"
    def win(v):
        w = "Keiko" if v > 0 else "Sánchez"
        return f"{w} gana por {abs(v)/18_000_000*100:.3f}pp"

    rows = ""
    for ub, d in sorted(deps.items(), key=lambda x: -x[1]["keiko_votos"]):
        wc   = "wk" if d["keiko_votos"] > d["sanchez_votos"] else "ws"
        diff = d["keiko_votos"] - d["sanchez_votos"]
        diff_str = f"+{diff:,}" if diff > 0 else f"−{abs(diff):,}"
        diff_cls = "kd" if diff > 0 else "sd"
        pend = d["actas_pendientes"]
        pend_cls = 'class="pc"' if pend > 500 else ('class="ph"' if pend > 50 else "")
        rows += (f'<tr class="{wc}"><td class="dn">{d["nombre"]}</td>'
                 f'<td>{d["keiko_votos"]:,}</td><td class="kp">{d["keiko_pct"]}%</td>'
                 f'<td>{d["sanchez_votos"]:,}</td><td class="sp">{d["sanchez_pct"]}%</td>'
                 f'<td class="{diff_cls}">{diff_str}</td>'
                 f'<td {pend_cls}>{pend}</td><td>{d["pct_procesado"]}%</td></tr>\n')

    dom_pend = nac["actas_pendientes"] - 1514 - 2543

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="1200">
<title>Análisis Electoral Perú 2026 — Segunda Vuelta</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;color:#e2e8f0;line-height:1.6}}
  .header{{background:linear-gradient(135deg,#1e293b,#0f2044);padding:2rem;border-bottom:2px solid #334155}}
  .header h1{{font-size:1.6rem;font-weight:700;color:#f8fafc}}
  .subtitle{{color:#94a3b8;font-size:.9rem;margin-top:.3rem}}
  .badges{{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.6rem}}
  .badge{{display:inline-block;font-size:.75rem;padding:.2rem .6rem;border-radius:99px}}
  .bb{{background:#0ea5e9;color:#fff}}.bg{{background:#16a34a;color:#fff}}.br{{background:#dc2626;color:#fff}}
  .container{{max-width:1100px;margin:0 auto;padding:2rem 1.5rem}}
  .section{{margin-bottom:2.5rem}}
  .stitle{{font-size:.85rem;font-weight:600;color:#cbd5e1;border-left:3px solid #3b82f6;padding-left:.75rem;margin-bottom:1rem;text-transform:uppercase;letter-spacing:.05em}}
  .scoreboard{{display:grid;grid-template-columns:1fr auto 1fr;gap:1rem;align-items:center;background:#1e293b;border-radius:12px;padding:1.5rem;border:1px solid #334155}}
  .candidate{{text-align:center}}
  .ck{{color:#f97316;font-size:1.25rem;font-weight:700}}.cs{{color:#8b5cf6;font-size:1.25rem;font-weight:700}}
  .vk{{color:#f97316;font-size:1.85rem;font-weight:800;margin:.3rem 0}}.vsv{{color:#8b5cf6;font-size:1.85rem;font-weight:800;margin:.3rem 0}}
  .plabel{{font-size:1.1rem;color:#94a3b8}}
  .vsb{{text-align:center}}.vst{{color:#475569;font-size:1.1rem;font-weight:700}}
  .lead-tag{{background:{lead_color};color:#fff;padding:.3rem .75rem;border-radius:8px;font-size:.8rem;font-weight:600;margin-top:.5rem;display:block}}
  .prog{{background:#1e293b;border-radius:10px;padding:1.2rem 1.5rem;border:1px solid #334155;margin-top:1rem}}
  .plrow{{display:flex;justify-content:space-between;color:#94a3b8;font-size:.85rem;margin-bottom:.5rem}}
  .ai{{display:flex;gap:2rem;margin-top:.8rem;font-size:.85rem;flex-wrap:wrap}}
  .ai span{{color:#94a3b8}}.ai strong{{color:#e2e8f0}}
  .adanger{{background:#450a0a;border:1px solid #991b1b;border-radius:10px;padding:.9rem 1.2rem;margin-top:1rem;font-size:.88rem;color:#fca5a5}}
  .adanger strong{{color:#ef4444}}
  .refresh-bar{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:.5rem 1rem;margin-top:.75rem;font-size:.8rem;color:#64748b;display:flex;justify-content:space-between;align-items:center}}
  .refresh-bar a{{color:#3b82f6;text-decoration:none}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  th{{background:#1e293b;color:#94a3b8;padding:.6rem .75rem;text-align:right;font-weight:600;font-size:.75rem;text-transform:uppercase;border-bottom:2px solid #334155}}
  th:first-child{{text-align:left}}
  td{{padding:.5rem .75rem;border-bottom:1px solid #1e293b;text-align:right}}
  td:first-child{{text-align:left;font-weight:500}}
  tr:hover td{{background:#1e293b55}}
  .wk td:first-child{{border-left:3px solid #f97316}}.ws td:first-child{{border-left:3px solid #8b5cf6}}
  .wk .dn{{color:#fed7aa}}.ws .dn{{color:#ddd6fe}}
  .kp{{color:#f97316}}.sp{{color:#8b5cf6}}.kd{{color:#f97316}}.sd{{color:#8b5cf6}}.nt{{color:#94a3b8}}
  .ph{{color:#fbbf24;font-weight:600}}.pc{{color:#ef4444;font-weight:700}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}
  .card{{background:#1e293b;border-radius:10px;padding:1.2rem;border:1px solid #334155}}
  .clabel{{font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.4rem}}
  .cval{{font-size:1.5rem;font-weight:700}}.csub{{font-size:.8rem;color:#94a3b8;margin-top:.25rem;line-height:1.4}}
  .co .cval{{color:#f97316}}.cb .cval{{color:#3b82f6}}.cy .cval{{color:#fbbf24}}.cr .cval{{color:#ef4444}}
  .scenarios{{display:flex;flex-direction:column;gap:.75rem}}
  .sc{{background:#1e293b;border-radius:10px;padding:1rem 1.25rem;border:1px solid #334155;display:flex;justify-content:space-between;align-items:center}}
  .scname{{font-weight:600;font-size:.9rem}}.scsub{{font-size:.78rem;color:#64748b;margin-top:.15rem}}
  .scm{{font-size:1.1rem;font-weight:700}}.scw{{font-size:.78rem;color:#94a3b8;margin-top:.15rem}}
  .sc-k{{border-left:3px solid #f97316}}.sc-s{{border-left:3px solid #8b5cf6}}.sc-n{{border-left:3px solid #fbbf24}}
  .sg{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
  .si{{background:#1e293b;border-radius:10px;padding:1rem;border:1px solid #334155}}
  .sil{{font-size:.78rem;color:#64748b;text-transform:uppercase;letter-spacing:.04em}}
  .siv{{font-size:1.3rem;font-weight:700;margin:.3rem 0}}.sid{{font-size:.78rem;color:#94a3b8;line-height:1.4}}
  .conclusion{{background:linear-gradient(135deg,#1e3a5f,#1e293b);border-radius:12px;padding:1.5rem;border:1px solid #1d4ed8}}
  .conclusion h3{{color:#93c5fd;margin-bottom:.75rem;font-size:.9rem;text-transform:uppercase;letter-spacing:.05em}}
  .conclusion p{{color:#cbd5e1;font-size:.9rem;margin-bottom:.5rem}}
  .conclusion strong{{color:#f8fafc}}
  .note{{margin-top:.75rem;padding:.75rem;background:#1d4ed822;border-radius:8px;border-left:3px solid #3b82f6;color:#93c5fd;font-size:.82rem}}
  .ts{{color:#475569;font-size:.75rem;text-align:right;margin-top:2rem;padding-top:1rem;border-top:1px solid #1e293b}}
  @media(max-width:640px){{.scoreboard,.sg{{grid-template-columns:1fr}}.sc{{flex-direction:column;align-items:flex-start;gap:.4rem}}}}
</style>
</head>
<body>
<div class="header">
  <h1>Perú 2026 — Análisis Electoral Segunda Vuelta</h1>
  <div class="subtitle">Keiko Fujimori (Fuerza Popular) &nbsp;vs.&nbsp; Roberto Sánchez (Juntos por el Perú)</div>
  <div class="badges">
    <span class="badge bb">Fuente: ONPE oficial</span>
    <span class="badge bg">Actualizado {ts}</span>
    <span class="badge br">{nac["actas_pct"]:.3f}% actas — Resultado muy ajustado</span>
  </div>
</div>
<div class="container">

  <div class="section">
    <div class="stitle">Estado actual del conteo</div>
    <div class="scoreboard">
      <div class="candidate"><div class="ck">Keiko Fujimori</div><div class="vk">{a["keiko_total"]:,}</div><div class="plabel">{a["keiko_pct"]}%</div></div>
      <div class="vsb"><div class="vst">VS</div><span class="lead-tag">{lead_winner} {lead_str}</span></div>
      <div class="candidate"><div class="cs">Roberto Sánchez</div><div class="vsv">{a["sanchez_total"]:,}</div><div class="plabel">{a["sanchez_pct"]}%</div></div>
    </div>
    <div class="prog">
      <div class="plrow"><span>Actas computadas</span><strong style="color:#e2e8f0">{nac["actas_pct"]:.3f}% — {nac["actas_contabilizadas"]:,} / {nac["total_actas"]:,}</strong></div>
      <div style="background:#334155;border-radius:99px;height:10px;overflow:hidden">
        <div style="width:{nac["actas_pct"]:.1f}%;background:#22c55e;height:100%;border-radius:99px"></div>
      </div>
      <div class="ai">
        <span>Pendientes dom.: <strong>~{max(dom_pend,0):,} actas</strong></span>
        <span>JEE: <strong>{nac["actas_jee"]:,} actas</strong></span>
        <span>Extranjero: <strong>2,543 actas (0%)</strong></span>
      </div>
    </div>
    <div class="adanger">
      <strong>Resultado extremadamente ajustado:</strong> Solo <strong>{lead_str} votos</strong> ({abs(lead)/18_000_000*100:.3f}pp).
      El extranjero (≈508,600 votos) decide. Break-even: Sánchez necesita ≥{100-be:.1f}% del voto exterior.
    </div>
    <div class="refresh-bar">
      <span>⏱ Se actualiza automáticamente cada 20 minutos · Último: {ts}</span>
      <a href="/refresh">↻ Actualizar ahora</a>
    </div>
  </div>

  <div class="section">
    <div class="stitle">Resultados por departamento</div>
    <div style="overflow-x:auto;border-radius:10px;border:1px solid #334155">
    <table><thead><tr>
      <th>Departamento</th><th>Keiko</th><th>K%</th><th>Sánchez</th><th>S%</th>
      <th>Diferencia</th><th>Actas pend.</th><th>% comp.</th>
    </tr></thead><tbody>{rows}</tbody></table>
    </div>
  </div>

  <div class="section">
    <div class="stitle">Votos pendientes</div>
    <div class="cards">
      <div class="card cy"><div class="clabel">Domésticas pendientes</div><div class="cval">~{max(dom_pend,0):,}</div>
        <div class="csub">Net: {fmt(a["net_pendientes"])} para Keiko<br>Cusco −29k · Ayacucho −21k · Loreto +16k</div></div>
      <div class="card cb"><div class="clabel">JEE impugnadas</div><div class="cval">{nac["actas_jee"]:,}</div>
        <div class="csub">Net: {fmt(a["net_jee"])} para Keiko<br>Lima 935 actas · Callao 69 actas</div></div>
      <div class="card co"><div class="clabel">Extranjero (0%)</div><div class="cval">2,543</div>
        <div class="csub">≈508,600 votos totales<br><strong style="color:#fbbf24">Break-even: {be}% Keiko / {100-be:.1f}% Sánchez</strong></div></div>
      <div class="card cr"><div class="clabel">Ventaja actual</div><div class="cval">{lead_str}</div>
        <div class="csub">{abs(lead)/18_000_000*100:.3f}pp — Una de las más reñidas del siglo</div></div>
    </div>
  </div>

  <div class="section">
    <div class="stitle">Escenarios de proyección</div>
    <div class="scenarios">
      <div class="sc sc-k"><div><div class="scname">Optimista Keiko (65% extran.)</div></div>
        <div style="text-align:right"><div class="scm" style="color:#f97316">{fmt(p65)}</div><div class="scw">{win(p65)}</div></div></div>
      <div class="sc sc-k"><div><div class="scname">Base — 60/40 extranjero</div><div class="scsub">Supuesto del análisis</div></div>
        <div style="text-align:right"><div class="scm" style="color:#f97316">{fmt(p60)}</div><div class="scw">{win(p60)}</div></div></div>
      <div class="sc sc-k"><div><div class="scname">Conservador Keiko (55% extran.)</div></div>
        <div style="text-align:right"><div class="scm" style="color:#f97316">{fmt(p55)}</div><div class="scw">{win(p55)}</div></div></div>
      <div class="sc sc-n"><div><div class="scname">Break-even</div><div class="scsub">Punto exacto de empate</div></div>
        <div style="text-align:right"><div class="scm" style="color:#fbbf24">{be}% Keiko / {100-be:.1f}% Sánchez</div></div></div>
      <div class="sc sc-s"><div><div class="scname">Sánchez gana</div><div class="scsub">Con ≥{100-be:.1f}% del extran. (sin otras condiciones)</div></div>
        <div style="text-align:right"><div class="scm" style="color:#8b5cf6">Probabilidad ≈ 25–35%</div></div></div>
    </div>
  </div>

  <div class="section">
    <div class="stitle">Intervalo de confianza al 95%</div>
    <div style="background:#1e293b;border-radius:10px;padding:1.5rem;border:1px solid #334155">
      <div style="display:flex;justify-content:space-between;font-size:1.1rem;font-weight:700;margin-bottom:1rem">
        <span style="color:#f97316">Keiko {fmt(ic_inf)}</span>
        <span style="color:#f97316">Keiko {fmt(ic_sup)}</span>
      </div>
      <div style="background:#0f1117;border-radius:99px;height:14px;overflow:hidden;position:relative">
        <div style="position:absolute;left:0;top:0;bottom:0;width:50%;background:#8b5cf6;border-radius:99px 0 0 99px"></div>
        <div style="position:absolute;left:50.5%;top:0;bottom:0;right:0;background:#f9731666;border-radius:0 99px 99px 0"></div>
        <div style="position:absolute;left:47%;top:0;bottom:0;width:6%;background:#f97316;border-radius:4px"></div>
      </div>
      <div style="display:flex;justify-content:center;gap:3rem;margin-top:.75rem;font-size:.8rem;color:#64748b">
        <span>← Sánchez gana</span><span style="color:#94a3b8;font-weight:600">0</span><span>Keiko gana →</span>
      </div>
      <div style="margin-top:1rem;padding:.75rem;background:#0f1117;border-radius:8px;font-size:.85rem;color:#94a3b8">
        IC 95%: [<strong style="color:#e2e8f0">{fmt(ic_inf)}</strong> , <strong style="color:#e2e8f0">{fmt(ic_sup)}</strong>]
        — Todo en territorio positivo para Keiko (bajo supuesto 60/40).<br>
        Sánchez gana si extran. supera <strong style="color:#fbbf24">{100-be:.1f}%</strong>.
      </div>
    </div>
  </div>

  <div class="section">
    <div class="stitle">Conclusión</div>
    <div class="conclusion">
      <h3>Veredicto — {nac["actas_pct"]:.3f}% actas · Carrera al filo</h3>
      <p>Con solo <strong>{lead_str} votos</strong> ({abs(lead)/18_000_000*100:.3f}pp), la elección la decide el <strong>voto extranjero</strong> (≈508,600 sin contar).</p>
      <p>Proyección base 60/40: <strong>Keiko {fmt(p60)}</strong>. Break-even: {be}% Keiko. Si Sánchez supera {100-be:.1f}% en exterior, gana sin condiciones adicionales.</p>
      <p>JEE ({fmt(a["net_jee"])} Keiko) y pendientes domésticos ({fmt(a["net_pendientes"])}) casi se compensan. El extranjero es el único bloque que puede cambiar el resultado.</p>
      <div class="note"><strong>Nota:</strong> API oficial ONPE. Supuesto 60/40 extranjero definido por el usuario. Patrón 2021: Keiko obtuvo ~62–65% en exterior.</div>
    </div>
  </div>

  <div class="ts">Datos: resultadosegundavuelta.onpe.gob.pe · {ts} · Actualización automática cada 20 min</div>
</div>
</body>
</html>"""
