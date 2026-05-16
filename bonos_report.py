"""
Reporte HTML de Bonos y Letras argentinos.

Uso:
    python bonos_report.py                       # filtros por defecto
    python bonos_report.py --out output/mi.html  # ruta personalizada
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

ROOT    = Path(__file__).parent
OUT_DIR = ROOT / "output"

# Rangos TIR razonables por categoría (fuera → se excluye del scatter, igual se muestra card)
TIR_RANGES: dict[str, tuple[float, float]] = {
    "hard_dollar": (-5.0,  30.0),
    "cer":         (-15.0, 20.0),
    "ars_fija":    (-5.0,  60.0),
    "ars_badlar":  (-5.0,  60.0),
    "dolar_link":  (-5.0,  20.0),   # TIR ARS — se muestra con caveat
    "dual":        (-15.0, 20.0),
}

CATEGORIA_LABEL: dict[str, str] = {
    "hard_dollar": "Hard Dollar (USD MEP)",
    "cer":         "CER / UVA (TIR real)",
    "ars_fija":    "ARS Tasa Fija",
    "ars_badlar":  "ARS BADLAR",
    "dolar_link":  "Dólar Link",
    "dual":        "Dual (CER / Dólar Link)",
}

CATEGORIA_COLOR: dict[str, str] = {
    "hard_dollar": "#2196F3",
    "cer":         "#FF9800",
    "ars_fija":    "#9C27B0",
    "ars_badlar":  "#009688",
    "dolar_link":  "#F44336",
    "dual":        "#795548",
}

CATEGORIA_TIR_LABEL: dict[str, str] = {
    "hard_dollar": "TIR USD (%)",
    "cer":         "TIR real — CER + spread (%)",
    "ars_fija":    "TIR ARS nominal (%)",
    "ars_badlar":  "TIR ARS nominal (%)",
    "dolar_link":  "TIR ARS nominal (⚠ no comparable entre categorías)",
    "dual":        "TIR real (%)",
}

_CSS = """
:root{--navy:#1f3a5f;--navy2:#2d5082;--bg:#f0f3f7;--card:#fff;--border:#dce3ec;
      --text:#2c3e50;--muted:#7f8c8d}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}
a{color:var(--navy);text-decoration:none}
a:hover{text-decoration:underline}
header{background:var(--navy);color:#fff;padding:24px 40px}
header h1{font-size:22px;font-weight:700}
header p{color:#a8c1e0;font-size:13px;margin-top:4px}
.cat-tabs{background:var(--navy2);padding:10px 40px;display:flex;gap:8px;flex-wrap:wrap}
.cat-tab{color:#cde;font-size:12px;padding:5px 14px;border-radius:4px;
         border:1px solid rgba(255,255,255,.2);cursor:pointer;transition:background .2s;text-decoration:none}
.cat-tab:hover,.cat-tab.active{background:rgba(255,255,255,.2);color:#fff}
main{max-width:1180px;margin:0 auto;padding:28px 20px}
.cat-section{display:none}
.cat-section.active{display:block}
.sec-title{font-size:17px;font-weight:700;color:var(--navy);margin:0 0 14px;
           padding-bottom:7px;border-bottom:2px solid var(--navy)}
.ov-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:36px}
.ov-table{width:100%;border-collapse:collapse;background:var(--card);border-radius:8px;
          overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.ov-table th{background:var(--navy);color:#fff;padding:9px 11px;text-align:left;
             font-size:11px;font-weight:600;letter-spacing:.4px;text-transform:uppercase}
.ov-table td{padding:8px 11px;border-bottom:1px solid var(--border);font-size:13px}
.ov-table tr:last-child td{border-bottom:none}
.ov-table tr:hover td{background:#f8fafc}
.card{background:var(--card);border-radius:10px;padding:26px;margin-bottom:28px;
      box-shadow:0 2px 8px rgba(0,0,0,.08);border:1px solid var(--border)}
.bond-hdr{display:flex;align-items:center;gap:14px;margin-bottom:16px;flex-wrap:wrap}
.ticker-badge{background:var(--navy);color:#fff;padding:5px 14px;border-radius:6px;
              font-size:17px;font-weight:700;white-space:nowrap}
.bond-desc{font-size:14px;font-weight:500;flex:1;min-width:0}
.tir-badge{background:#e8f5e9;color:#1b5e20;padding:5px 13px;border-radius:20px;
           font-weight:700;font-size:15px;white-space:nowrap;border:1px solid #a5d6a7}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:16px}
@media(max-width:680px){.grid2{grid-template-columns:1fr}}
.info-tbl{width:100%;border-collapse:collapse}
.info-tbl thead tr th{background:var(--navy);color:#fff;padding:8px 10px;text-align:left;
                       font-size:11px;font-weight:600;letter-spacing:.3px;text-transform:uppercase}
.info-tbl td{padding:6px 9px;border-bottom:1px solid var(--border);font-size:12px;vertical-align:top}
.info-tbl td:first-child{color:var(--muted);font-weight:500;width:48%}
.info-tbl td:last-child{font-weight:600}
.info-tbl tr:last-child td{border-bottom:none}
.chart-wrap{border-radius:6px;overflow:hidden}
.narr{background:#f8fafc;border-left:3px solid var(--navy);padding:11px 15px;
      border-radius:0 6px 6px 0;font-size:13px;color:#34495e;margin-bottom:16px;line-height:1.75}
.warn-box{background:#fff8e1;border-left:3px solid #f39c12;padding:10px 15px;
          border-radius:0 6px 6px 0;font-size:12px;color:#7f4800;margin-bottom:12px}
.sim-section{margin-top:20px;padding-top:16px;border-top:1px solid var(--border)}
.sim-hdr{font-size:13px;font-weight:700;color:var(--navy);margin-bottom:10px}
.sim-controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.sim-label{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px}
.sim-input{border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:13px;width:130px;color:var(--text)}
.sim-btn{background:var(--navy);color:#fff;border:none;border-radius:5px;padding:6px 16px;font-size:12px;font-weight:600;cursor:pointer}
.sim-btn:hover{background:var(--navy2)}
.sim-result{font-size:12px;margin-top:10px;padding:10px 14px;background:#f0f8f3;border-left:3px solid #27ae60;border-radius:0 6px 6px 0;line-height:1.8}
.bond-note{font-size:12px;color:var(--muted);margin-bottom:14px;line-height:1.6;padding:0 2px}
.chart-title{font-size:12px;font-weight:600;color:var(--text);margin-bottom:6px;text-align:center}
.chart-wrap{width:100%}
.footnote{font-size:11px;color:var(--muted);text-align:center;margin-top:36px;
          padding-top:16px;border-top:1px solid var(--border);line-height:1.8}
@media(max-width:600px){
  header{padding:16px 14px}
  header h1{font-size:18px}
  .cat-tabs{padding:8px 12px;gap:6px}
  main{padding:16px 10px}
  .card{padding:16px 14px}
  .bond-hdr{gap:8px}
  .ticker-badge{font-size:14px;padding:4px 10px}
  .sim-input{width:110px}
  .sim-controls{gap:8px}
}
"""

_JS = r"""
function showCat(cat) {
  document.querySelectorAll('.cat-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.cat-tab').forEach(t => t.classList.remove('active'));
  const sec = document.getElementById('cat-' + cat);
  if (sec) sec.classList.add('active');
  document.querySelectorAll('.cat-tab[data-cat="' + cat + '"]').forEach(t => t.classList.add('active'));
}

function runSim(ticker) {
  const rawEl = document.getElementById('simdata-' + ticker);
  if (!rawEl) return;
  const { flows, tir, price, vn_min, currency } = JSON.parse(rawEl.textContent);

  const amount = parseFloat(document.getElementById('simamt-' + ticker).value) || 0;
  if (amount <= 0) return;

  const today = new Date(); today.setHours(0,0,0,0);
  const sf = flows
    .filter(f => new Date(f.fecha) > today)
    .sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
  if (!sf.length) return;

  const pricePerVN = price / 100;
  const vnBought = Math.floor(amount / pricePerVN / vn_min) * vn_min;
  const resultEl = document.getElementById('simresult-' + ticker);
  resultEl.style.display = '';
  if (vnBought <= 0) {
    resultEl.innerHTML = '⚠ Monto insuficiente. Mínimo estimado: ' + currency + ' ' +
      Math.ceil(vn_min * pricePerVN).toLocaleString('es-AR');
    return;
  }

  let vnHeld = vnBought;
  let cashPool = amount - vnBought * pricePerVN;

  function theoPrice(atDate, futureFlows) {
    return futureFlows.reduce((s, f) => {
      const days = (new Date(f.fecha) - atDate) / 86400000;
      return days > 0 ? s + f.total / Math.pow(1 + tir, days / 365) : s;
    }, 0);
  }

  const lastDate = new Date(sf[sf.length - 1].fecha);
  const totalDays = Math.ceil((lastDate - today) / 86400000);
  const xs = [], ys = [];
  let flowIdx = 0;

  for (let d = 0; d <= totalDays; d++) {
    const cur = new Date(today.getTime() + d * 86400000);
    while (flowIdx < sf.length && new Date(sf[flowIdx].fecha) <= cur) {
      const after = sf.slice(flowIdx + 1);
      cashPool += sf[flowIdx].total * vnHeld / 100;
      const tp = theoPrice(new Date(sf[flowIdx].fecha), after);
      if (tp > 0 && after.length > 0) {
        const moreVN = Math.floor(cashPool / (tp / 100) / vn_min) * vn_min;
        if (moreVN > 0) { vnHeld += moreVN; cashPool -= moreVN * tp / 100; }
      }
      flowIdx++;
    }
    xs.push(cur.toISOString().slice(0, 10));
    ys.push(vnHeld * theoPrice(cur, sf.slice(flowIdx)) / 100 + cashPool);
  }

  const finalVal = ys[ys.length - 1];
  const retPct = ((finalVal / amount - 1) * 100).toFixed(1);
  const fmt = v => Math.round(v).toLocaleString('es-AR');

  Plotly.newPlot(
    document.getElementById('simchart-' + ticker),
    [{ x: xs, y: ys, type: 'scatter', mode: 'lines',
       line: { color: '#27ae60', width: 2 },
       hovertemplate: '%{x|%d %b %Y}: <b>' + currency + ' %{y:,.0f}</b><extra></extra>' }],
    { height: 240, template: 'plotly_white',
      margin: { t: 15, b: 40, l: 65, r: 15 },
      xaxis: { tickformat: '%b %Y' },
      yaxis: { tickformat: ',.0f', tickprefix: currency + ' ' },
      font: { size: 11 }, showlegend: false },
    { displayModeBar: false, responsive: true }
  );

  resultEl.innerHTML =
    'Invertís <strong>' + currency + ' ' + fmt(amount) + '</strong>' +
    ' &middot; VN comprado: <strong>' + currency + ' ' + fmt(vnBought) + '</strong>' +
    ' &middot; Sobrante: ' + currency + ' ' + fmt(amount - vnBought * pricePerVN) +
    '<br>Valor final reinvirtiendo cupones: <strong>' + currency + ' ' + fmt(finalVal) + '</strong>' +
    ' <em>(' + (parseFloat(retPct) >= 0 ? '+' : '') + retPct + '% sobre inversión inicial)</em>';
}

window.addEventListener('load', () => {
  const first = document.querySelector('.cat-tab');
  if (first) showCat(first.dataset.cat);
});
"""


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE FLUJOS
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_flujos(flujos_raw) -> pd.DataFrame:
    raw = json.loads(flujos_raw) if isinstance(flujos_raw, str) else (flujos_raw or [])
    today = pd.Timestamp.now().normalize()
    rows = []
    for f in raw:
        ts = pd.to_datetime(f.get("fechaCorte", ""), errors="coerce")
        if pd.isna(ts):
            continue
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
        fecha = ts.normalize()
        if fecha < today:
            continue
        renta = float(f.get("renta") or f.get("interes") or 0)
        amort = float(f.get("amortizacion") or 0)
        total = float(f.get("total") or 0)
        if total <= 0:
            continue
        rows.append({"fecha": fecha, "renta": renta, "amortizacion": amort, "total": total})
    if not rows:
        return pd.DataFrame(columns=["fecha", "renta", "amortizacion", "total"])
    return pd.DataFrame(rows).sort_values("fecha").reset_index(drop=True)


def _row_html(k: str, v: str) -> str:
    return f"<tr><td>{k}</td><td>{v}</td></tr>"


# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICO TIR vs VENCIMIENTO POR CATEGORÍA
# ═══════════════════════════════════════════════════════════════════════════════

def _dotplot_html(cat: str, df_cat: pd.DataFrame) -> str:
    import numpy as np

    color = CATEGORIA_COLOR.get(cat, "#607D8B")
    tir_label = CATEGORIA_TIR_LABEL.get(cat, "TIR (%)")
    tir_min, tir_max = TIR_RANGES.get(cat, (-10, 50))

    df = df_cat.copy()
    df["fechaVencimiento"] = pd.to_datetime(df["fechaVencimiento"])
    vol = df["volumen"].fillna(0).clip(lower=0)
    vol_max = vol.max() if vol.max() > 0 else 1
    df["_size"] = 8 + 20 * np.sqrt(vol / vol_max)

    # Separar en rango y fuera de rango
    in_range  = df[df["tir_pct"].between(tir_min, tir_max)]
    out_range = df[~df["tir_pct"].between(tir_min, tir_max)]

    fig = go.Figure()

    if not out_range.empty:
        fig.add_trace(go.Scatter(
            x=out_range["fechaVencimiento"],
            y=out_range["tir_pct"],
            mode="markers",
            name="Fuera de rango",
            marker=dict(size=6, color="#cccccc", opacity=0.5),
            customdata=out_range[["ticker", "tir_pct", "emisor"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b>  %{customdata[2]}<br>"
                "TIR: %{customdata[1]:.2f}%<br>"
                "Vto: %{x|%d/%m/%Y}<extra></extra>"
            ),
        ))

    if not in_range.empty:
        fig.add_trace(go.Scatter(
            x=in_range["fechaVencimiento"],
            y=in_range["tir_pct"],
            mode="markers+text",
            name=CATEGORIA_LABEL.get(cat, cat),
            marker=dict(
                size=in_range["_size"].tolist(),
                color=color,
                line=dict(width=1.5, color="white"),
                opacity=0.9,
            ),
            text=in_range["ticker"],
            textposition="top center",
            textfont=dict(size=9),
            customdata=in_range[["ticker", "emisor", "price", "volumen", "moneda_cotizacion"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b>  %{customdata[1]}<br>"
                "TIR: <b>%{y:.2f}%</b>  ·  Vto: %{x|%d/%m/%Y}<br>"
                "Precio: %{customdata[2]:,.2f}  ·  Vol: %{customdata[3]:,.0f}<br>"
                "Cotiza en: %{customdata[4]}<extra></extra>"
            ),
        ))

    fig.update_layout(
        height=380,
        template="plotly_white",
        margin=dict(t=20, b=40, l=60, r=15),
        xaxis=dict(title="Fecha de vencimiento", tickformat="%b %Y"),
        yaxis=dict(title=tir_label, ticksuffix="%"),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.02, yanchor="bottom"),
        font=dict(size=11),
        hovermode="closest",
    )
    return pio.to_html(
        fig, full_html=False, include_plotlyjs=False,
        config={"displayModeBar": False},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICO DE FLUJOS DE PAGOS
# ═══════════════════════════════════════════════════════════════════════════════

def _payment_chart(row: pd.Series) -> str:
    fl = _parse_flujos(row["flujos"])
    if fl.empty:
        return "<p style='color:gray;padding:12px'>Sin flujos futuros disponibles.</p>"

    total_pago = fl["total"].sum()
    title_html = (
        f'<p class="chart-title">Flujo de pagos futuros &nbsp;·&nbsp; '
        f'Total restante: <strong>{total_pago:.2f}</strong> por c/100 VN</p>'
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Renta", x=fl["fecha"], y=fl["renta"],
        marker_color="#4472CA",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Renta: <b>%{y:.4f}</b> / 100 VN<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Amortización", x=fl["fecha"], y=fl["amortizacion"],
        marker_color="#70AD47",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Amortización: <b>%{y:.4f}</b> / 100 VN<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack", height=260, template="plotly_white",
        autosize=True,
        margin=dict(t=40, b=45, l=65, r=20),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.0, yanchor="bottom"),
        xaxis=dict(
            title="Fecha de pago",
            tickmode="array",
            tickvals=fl["fecha"].tolist(),
            ticktext=[d.strftime("%-d %b %Y") for d in fl["fecha"]],
            tickangle=-45,
        ),
        yaxis=dict(title="Pago por c/100 VN"),
        font=dict(size=11),
    )
    chart_html = pio.to_html(
        fig, full_html=False, include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
    )
    return title_html + chart_html


# ═══════════════════════════════════════════════════════════════════════════════
# CARD DE BONO
# ═══════════════════════════════════════════════════════════════════════════════

def _bond_card_html(row: pd.Series) -> str:
    ticker  = str(row["ticker"])
    desc    = str(row.get("descripcion", ""))
    emisor  = str(row.get("emisor") or "—")
    tir     = float(row["tir_pct"])
    price   = float(row.get("price") or 0)
    vto     = str(row["fechaVencimiento"])[:10]
    cotiz   = str(row.get("moneda_cotizacion", ""))
    vol     = float(row.get("volumen") or 0)
    dur     = row.get("modified_duration")
    paridad = row.get("paridad")
    vt      = row.get("valor_tecnico")
    curr    = "USD" if cotiz == "USD MEP" else "ARS"
    cat     = str(row.get("categoria", ""))
    tir_lbl = CATEGORIA_TIR_LABEL.get(cat, "TIR (%)")

    vn_min = float(row.get("lamina_minima") or 1.0)
    min_inv = price * (vn_min / 100)

    # Narrativa simple (sin balance)
    texto_intereses = str(row.get("texto_intereses") or "")
    texto_amort     = str(row.get("texto_amortizacion") or "")
    narrativa = ""
    if texto_intereses:
        narrativa += f"<strong>Cupón:</strong> {texto_intereses} "
    if texto_amort:
        narrativa += f"<strong>Amortización:</strong> {texto_amort}"

    # Caveat dólar-link
    warn_html = ""
    if cat == "dolar_link":
        warn_html = (
            '<div class="warn-box">⚠ <strong>Dólar Link</strong>: '
            'la TIR mostrada es la tasa nominal en ARS y no es comparable con otras categorías. '
            'El rendimiento real depende de la evolución del tipo de cambio oficial.</div>'
        )

    btbl = (
        _row_html("Emisor", emisor[:42]) +
        _row_html("Legislación", str(row.get("legislacion") or "—")) +
        _row_html("Vencimiento", vto) +
        _row_html("Precio actual", f"{price:.2f}") +
        _row_html(tir_lbl, f"<strong>{tir:.2f}%</strong>") +
        _row_html("Cotiza en", cotiz) +
        _row_html("VN mínimo", f"{curr} {vn_min:,.0f}") +
        _row_html("Inversión mínima est.", f"<strong>{curr} {min_inv:,.0f}</strong>") +
        _row_html("Volumen reciente op.", f"{vol:,.0f}")
    )

    mtbl = ""
    if dur is not None and not pd.isna(dur):
        mtbl += _row_html("Duration modificada", f"{dur:.2f}")
    if paridad is not None and not pd.isna(paridad):
        mtbl += _row_html("Paridad", f"{float(paridad)*100:.1f}%")
    if vt is not None and not pd.isna(vt):
        mtbl += _row_html("Valor técnico", f"{float(vt):.4f}")

    mtbl_section = (
        f"<table class='info-tbl' style='margin-top:0'>"
        f"<thead><tr><th colspan='2'>Métricas de mercado</th></tr></thead>"
        f"<tbody>{mtbl}</tbody></table>"
    ) if mtbl else ""

    # Simulación
    fl_df = _parse_flujos(row["flujos"])
    sim_flows = [
        {"fecha": r["fecha"].strftime("%Y-%m-%d"), "total": round(float(r["total"]), 8)}
        for _, r in fl_df.iterrows()
    ]
    sim_data = json.dumps(
        {"flows": sim_flows, "tir": round(float(row["tir"]), 8),
         "price": round(float(price), 6), "vn_min": float(vn_min), "currency": curr},
        ensure_ascii=False,
    )
    default_inv = max(int(vn_min * price / 100), 1000)

    narr_html = f'<p class="bond-note">{narrativa}</p>' if narrativa else ""

    return f"""<section class="card" id="{ticker}" data-ticker="{ticker}">
  <div class="bond-hdr">
    <span class="ticker-badge">{ticker}</span>
    <span class="bond-desc">{desc}</span>
    <span class="tir-badge">TIR {tir:.2f}%</span>
  </div>
  {narr_html}
  {warn_html}
  <div class="grid2">
    <div>
      <table class="info-tbl">
        <thead><tr><th colspan="2">Datos del bono</th></tr></thead>
        <tbody>{btbl}</tbody>
      </table>
    </div>
    <div>{mtbl_section}</div>
  </div>
  <div class="chart-wrap">{_payment_chart(row)}</div>
  <div class="sim-section">
    <script type="application/json" id="simdata-{ticker}">{sim_data}</script>
    <p class="sim-hdr">Simulación: reinversión de cupones al rendimiento actual</p>
    <div class="sim-controls">
      <label class="sim-label">Monto a invertir ({curr})
        <input type="number" class="sim-input" id="simamt-{ticker}"
               value="{default_inv}" min="0"
               onkeypress="if(event.key==='Enter')runSim('{ticker}')">
      </label>
      <button class="sim-btn" onclick="runSim('{ticker}')">Simular</button>
    </div>
    <div id="simchart-{ticker}"></div>
    <p id="simresult-{ticker}" class="sim-result" style="display:none"></p>
  </div>
</section>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# TABLA RESUMEN POR CATEGORÍA
# ═══════════════════════════════════════════════════════════════════════════════

def _overview_html(df_cat: pd.DataFrame, cat: str) -> str:
    curr_map = {"USD MEP": "USD", "ARS": "ARS"}
    rows_html = ""
    for _, r in df_cat.iterrows():
        curr = curr_map.get(str(r.get("moneda_cotizacion", "")), "")
        price = float(r.get("price") or 0)
        vn_min = float(r.get("lamina_minima") or 1.0)
        min_inv = price * (vn_min / 100)
        rows_html += f"""<tr>
          <td><a href="#{r['ticker']}">{r['ticker']}</a></td>
          <td>{str(r.get('emisor') or '—')[:34]}</td>
          <td><strong>{float(r['tir_pct']):.2f}%</strong></td>
          <td>{str(r['fechaVencimiento'])[:10]}</td>
          <td>{price:.2f}</td>
          <td><strong>~{curr} {min_inv:,.0f}</strong></td>
          <td>{float(r.get('modified_duration') or 0):.2f}</td>
        </tr>"""
    tir_lbl = CATEGORIA_TIR_LABEL.get(cat, "TIR (%)")
    return f"""
<h2 class="sec-title">Resumen — {CATEGORIA_LABEL.get(cat, cat)}</h2>
<div class="ov-table-wrap">
<table class="ov-table">
  <thead><tr>
    <th>Ticker</th><th>Emisor</th><th>{tir_lbl}</th><th>Vencimiento</th>
    <th>Precio</th><th>Inversión mín. est.</th><th>Duration mod.</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN DEL REPORTE HTML
# ═══════════════════════════════════════════════════════════════════════════════

def build_html_report(df: pd.DataFrame) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = pd.Timestamp.now().normalize()

    # Orden de las categorías en las tabs
    cat_order = ["hard_dollar", "cer", "ars_fija", "ars_badlar", "dolar_link", "dual"]
    cats_present = [c for c in cat_order if c in df["categoria"].values]

    tabs_html = ""
    for cat in cats_present:
        n = (df["categoria"] == cat).sum()
        tabs_html += f'<a class="cat-tab" data-cat="{cat}" onclick="showCat(\'{cat}\')">{CATEGORIA_LABEL[cat]} <span style="opacity:.7;font-size:11px">({n})</span></a>'

    sections_html = ""
    for cat in cats_present:
        df_cat = df[df["categoria"] == cat].copy()
        df_cat = df_cat[df_cat["fechaVencimiento"] >= today]
        df_cat = df_cat.sort_values("tir_pct", ascending=False).reset_index(drop=True)

        # Scatter solo de bonds con TIR en rango razonable
        scatter = _dotplot_html(cat, df_cat)
        overview = _overview_html(df_cat, cat)

        # Cards de todos los bonds de la categoría
        cards = "".join(_bond_card_html(r) for _, r in df_cat.iterrows())

        sections_html += f"""<div class="cat-section" id="cat-{cat}">
  <div class="card" style="padding:16px 20px;margin-bottom:28px">
    {scatter}
  </div>
  {overview}
  <h2 class="sec-title">Detalle por bono</h2>
  {cards}
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Bonos y Letras Argentina — {ts}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
  <style>{_CSS}</style>
</head>
<body>
<div style="background:#152c4a;padding:7px 40px;font-size:12px">
  <a href="index.html" style="color:#a8c1e0;text-decoration:none">← Obligaciones Negociables</a>
</div>
<header>
  <h1>Bonos y Letras Argentina</h1>
  <p>Hard Dollar · CER · ARS Fija · BADLAR · Dólar Link &nbsp;·&nbsp; Datos al {ts}</p>
</header>
<div class="cat-tabs">{tabs_html}</div>
<main>
  {sections_html}
  <p class="footnote">
    Datos de TIR y precios: PPI (Portfolio Personal Inversiones).<br>
    TIR hard dollar en USD nominal. TIR CER en términos reales (CER + spread).
    TIR ARS en pesos nominales. TIR dólar-link en ARS nominal (no comparable con otras categorías).<br>
    Inversión mínima estimada: precio × VN mínimo. Verificar lámina mínima y lote con el broker antes de operar.<br>
    Este reporte es de carácter informativo y no constituye asesoramiento financiero.
  </p>
</main>
<script>{_JS}</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--in",  dest="input", default=str(OUT_DIR / "bonos_tir.parquet"))
    parser.add_argument("--out", dest="output", default=None)
    args = parser.parse_args()

    tir_path = Path(args.input)
    if not tir_path.exists():
        raise FileNotFoundError(f"No se encontró: {tir_path}\nCorré primero: python fetch_bonos.py")

    print(f"Cargando {tir_path.name}...")
    df = pd.read_parquet(tir_path)
    df["flujos"] = df["flujos"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else x
    )
    df["fechaVencimiento"] = pd.to_datetime(df["fechaVencimiento"], errors="coerce", utc=True).dt.tz_convert(None)
    print(f"  {len(df)} bonds  |  categorías: {df['categoria'].value_counts().to_dict()}")

    print("Generando reporte HTML...")
    html = build_html_report(df)

    out = Path(args.output) if args.output else OUT_DIR / "bonos_report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Reporte guardado: {out}  ({out.stat().st_size / 1024:.1f} KB)")

    docs = ROOT / "docs" / "bonos.html"
    if docs.parent.exists():
        import shutil
        shutil.copy2(out, docs)
        print(f"Copiado a:        {docs}")
