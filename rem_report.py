"""
Reporte HTML del REM — análisis de break-even pesos vs dólares.

Uso:
    python rem_report.py                    # lee output/rem_*.parquet
    python rem_report.py --out mi.html      # ruta personalizada
    python rem_report.py --usd-yield 5.0    # TNA USD asumida (default: 0%)

Salida: docs/rem_report.html
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

ROOT    = Path(__file__).parent
OUT_DIR = ROOT / "output"

# TC base estimado al momento de la encuesta más reciente (ARS/USD spot mayo-2026)
# Aproximado a partir del Q10 del primer mes forward y el crawling peg histórico (~1%/mes)
TC_BASE_DEFAULT = 1400.0


# ── CSS / JS ──────────────────────────────────────────────────────────────────

_CSS = """
:root{--navy:#1f3a5f;--navy2:#2d5082;--bg:#f0f3f7;--card:#fff;--border:#dce3ec;
      --text:#2c3e50;--muted:#7f8c8d;--green:#27ae60;--red:#e74c3c;--orange:#f39c12}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}
header{background:var(--navy);color:#fff;padding:24px 40px}
header h1{font-size:22px;font-weight:700}
header p{color:#a8c1e0;font-size:13px;margin-top:4px}
main{max-width:1140px;margin:0 auto;padding:28px 20px}
.card{background:var(--card);border-radius:10px;padding:26px;margin-bottom:28px;
      box-shadow:0 2px 8px rgba(0,0,0,.08);border:1px solid var(--border)}
.sec-title{font-size:17px;font-weight:700;color:var(--navy);margin:0 0 14px;
           padding-bottom:7px;border-bottom:2px solid var(--navy)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}
@media(max-width:720px){.grid2{grid-template-columns:1fr}}
/* summary cards */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}
@media(max-width:900px){.kpi-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:500px){.kpi-grid{grid-template-columns:1fr}}
.kpi{background:var(--card);border-radius:10px;padding:18px 20px;
     box-shadow:0 1px 4px rgba(0,0,0,.08);border:1px solid var(--border);text-align:center}
.kpi-val{font-size:26px;font-weight:700;margin-bottom:4px}
.kpi-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:3px}
.green{color:var(--green)} .red{color:var(--red)} .orange{color:var(--orange)}
/* tabla resumen */
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl{width:100%;border-collapse:collapse;background:var(--card)}
.tbl th{background:var(--navy);color:#fff;padding:9px 12px;text-align:left;
        font-size:11px;font-weight:600;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap}
.tbl td{padding:8px 12px;border-bottom:1px solid var(--border);font-size:13px;white-space:nowrap}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:#f8fafc}
.badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700}
.badge-green{background:#e8f5e9;color:#1b5e20;border:1px solid #a5d6a7}
.badge-red{background:#ffebee;color:#b71c1c;border:1px solid #ef9a9a}
.badge-orange{background:#fff3e0;color:#e65100;border:1px solid #ffcc02}
/* explicación */
.explain{background:#f0f4fa;border-left:3px solid var(--navy);padding:12px 16px;
         border-radius:0 6px 6px 0;font-size:13px;color:#34495e;margin-bottom:20px;line-height:1.75}
.warn-box{background:#fff8e1;border-left:3px solid var(--orange);padding:10px 15px;
          border-radius:0 6px 6px 0;font-size:12px;color:#7f4800;margin-top:16px}
.footnote{font-size:11px;color:var(--muted);text-align:center;margin-top:36px;
          padding-top:16px;border-top:1px solid var(--border);line-height:1.8}
@media(max-width:600px){
  header{padding:16px 14px} header h1{font-size:18px}
  main{padding:16px 10px} .card{padding:16px 14px}
}
"""



# ── utilidades de Plotly ───────────────────────────────────────────────────────

def _fig_to_html(fig: go.Figure, height: int = 380) -> str:
    fig.update_layout(
        height=height,
        margin=dict(l=50, r=20, t=30, b=50),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font_family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        font_color="#2c3e50",
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False, config={"responsive": True})


def _navy(alpha: float = 1.0) -> str:
    return f"rgba(31,58,95,{alpha})"


# ── cálculo de métricas ────────────────────────────────────────────────────────

def compute_metrics(df_exp: pd.DataFrame, tc_base: float, usd_yield_tna: float) -> pd.DataFrame:
    """
    Devuelve un DataFrame con métricas break-even para cada mes del forward curve.

    Columnas:
      horizonte, ipc_pct, tamar_tem_pct, devaluation_pct,
      be_nominal_pct, be_real_pct, spread_pct, gana_pesos
    """
    # Filtrar sólo filas mensuales (fechas concretas)
    ipc   = df_exp[(df_exp.variable == "ipc")   & (df_exp.horizonte_tipo == "mensual")].copy()
    tamar = df_exp[(df_exp.variable == "tamar") & (df_exp.horizonte_tipo == "mensual")].copy()
    tc    = df_exp[(df_exp.variable == "tc")    & (df_exp.horizonte_tipo == "mensual")].copy()

    ipc   = ipc.set_index("horizonte").sort_index()
    tamar = tamar.set_index("horizonte").sort_index()
    tc    = tc.set_index("horizonte").sort_index()

    # TC: construir serie incluyendo base (mes previo al primer forward)
    tc_level = tc["mediana"].copy()
    prev_date = tc_level.index[0] - pd.DateOffset(months=1)
    prev_date = prev_date + pd.offsets.MonthEnd(0)
    tc_extendida = pd.concat([
        pd.Series([tc_base], index=[prev_date]),
        tc_level,
    ])
    devaluation = tc_extendida.pct_change().dropna() * 100  # en %

    # TC percentiles para dispersión
    tc_p25 = tc["p25"].copy()
    tc_p75 = tc["p75"].copy()
    tc_ex_p25 = pd.concat([pd.Series([tc_base], index=[prev_date]), tc_p25])
    tc_ex_p75 = pd.concat([pd.Series([tc_base * 1.01], index=[prev_date]), tc_p75])
    dev_p25 = tc_ex_p25.pct_change().dropna() * 100
    dev_p75 = tc_ex_p75.pct_change().dropna() * 100

    # Rendimiento mensual USD asumido (desde TNA anual)
    usd_monthly = usd_yield_tna / 12

    months = sorted(set(ipc.index) & set(tamar.index) & set(devaluation.index))

    rows = []
    for m in months:
        ipc_m    = ipc.at[m, "mediana"]     # % mensual
        ipc_p25  = ipc.at[m, "p25"]
        ipc_p75  = ipc.at[m, "p75"]
        tamar_m  = tamar.at[m, "mediana"] / 12   # TNA → TEM
        tamar_p25 = tamar.at[m, "p25"] / 12
        tamar_p75 = tamar.at[m, "p75"] / 12
        dev_m    = devaluation.get(m, float("nan"))
        dev_m_p25 = dev_p25.get(m, float("nan"))
        dev_m_p75 = dev_p75.get(m, float("nan"))

        # Break-even nominal: TEM en pesos que iguala retorno USD
        # be_nom = (1 + usd_monthly/100) * (1 + dev_m/100) - 1, en %
        be_nom = ((1 + usd_monthly / 100) * (1 + dev_m / 100) - 1) * 100

        # Break-even real: el anterior deflactado por inflación
        # Responde: ¿cuánto más que la inflación necesitás ganar en pesos para igualar USD?
        be_real = ((1 + be_nom / 100) / (1 + ipc_m / 100) - 1) * 100

        # Spread: cuánto pagan los pesos por encima del break-even
        spread = tamar_m - be_nom

        # Tasa real implícita en pesos (TAMAR deflactada por IPC)
        tasa_real_pesos = ((1 + tamar_m / 100) / (1 + ipc_m / 100) - 1) * 100

        rows.append({
            "horizonte":       m,
            "mes_label":       m.strftime("%b %Y"),
            "ipc_pct":         ipc_m,
            "ipc_p25":         ipc_p25,
            "ipc_p75":         ipc_p75,
            "tamar_tem_pct":   tamar_m,
            "tamar_tem_p25":   tamar_p25,
            "tamar_tem_p75":   tamar_p75,
            "devaluation_pct": dev_m,
            "dev_p25":         dev_m_p25,
            "dev_p75":         dev_m_p75,
            "be_nominal_pct":  be_nom,
            "be_real_pct":     be_real,
            "spread_pct":      spread,
            "tasa_real_pesos": tasa_real_pesos,
            "gana_pesos":      spread > 0,
        })

    return pd.DataFrame(rows)


# ── gráfico 1: inflación mensual esperada ────────────────────────────────────

def chart_ipc(m: pd.DataFrame) -> str:
    labels = m["mes_label"].tolist()
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels,
        y=m["ipc_pct"],
        name="IPC mensual (mediana)",
        marker_color="#e67e22",
        error_y=dict(
            type="data",
            symmetric=False,
            array=(m["ipc_p75"] - m["ipc_pct"]).tolist(),
            arrayminus=(m["ipc_pct"] - m["ipc_p25"]).tolist(),
            color="#d35400",
            thickness=2,
            width=6,
        ),
    ))

    fig.update_layout(
        yaxis_title="Var. % mensual",
        yaxis_ticksuffix="%",
        xaxis_title="Mes",
        showlegend=False,
        title_text="",
    )
    return _fig_to_html(fig, 340)


# ── gráfico 2: devaluación mensual esperada ──────────────────────────────────

def chart_devaluation(m: pd.DataFrame) -> str:
    labels = m["mes_label"].tolist()
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels,
        y=m["devaluation_pct"],
        name="Devaluación mensual",
        marker_color="#2980b9",
        error_y=dict(
            type="data",
            symmetric=False,
            array=(m["dev_p75"] - m["devaluation_pct"]).tolist(),
            arrayminus=(m["devaluation_pct"] - m["dev_p25"]).tolist(),
            color="#1a6fa0",
            thickness=2,
            width=6,
        ),
    ))

    fig.update_layout(
        yaxis_title="Var. % mensual TC nominal",
        yaxis_ticksuffix="%",
        xaxis_title="Mes",
        showlegend=False,
    )
    return _fig_to_html(fig, 340)


# ── gráfico 3: break-even rates (el corazón) ─────────────────────────────────

def chart_breakeven(m: pd.DataFrame, usd_yield_tna: float) -> str:
    labels = m["mes_label"].tolist()
    xs = labels + labels[::-1]

    # Relleno verde/rojo entre TAMAR y break-even
    tamar_vals  = m["tamar_tem_pct"].tolist()
    be_nom_vals = m["be_nominal_pct"].tolist()

    # Separar meses donde pesos ganan (verde) vs pierden (rojo)
    fill_above_y = []  # TAMAR cuando gana pesos, be_nom en reversa
    fill_below_y = []  # be_nom cuando gana pesos, TAMAR en reversa

    fig = go.Figure()

    # Sombrear cada mes: verde donde pesos ganan, rojo donde USD gana
    for i, (_, row) in enumerate(m.iterrows()):
        fillcolor = "rgba(39,174,96,0.10)" if row.gana_pesos else "rgba(231,76,60,0.08)"
        fig.add_vrect(x0=i - 0.5, x1=i + 0.5, fillcolor=fillcolor, line_width=0, layer="below")

    # Línea: TAMAR TEM
    fig.add_trace(go.Scatter(
        x=labels, y=tamar_vals,
        mode="lines+markers",
        name="TAMAR (TEM mensual)",
        line=dict(color="#27ae60", width=3),
        marker=dict(size=7),
    ))

    # Línea: break-even nominal
    usd_label = f"Break-even nominal (USD +{usd_yield_tna:.0f}% TNA)" if usd_yield_tna > 0 else "Break-even nominal (sin rendimiento USD)"
    fig.add_trace(go.Scatter(
        x=labels, y=be_nom_vals,
        mode="lines+markers",
        name=usd_label,
        line=dict(color="#e74c3c", width=3, dash="dash"),
        marker=dict(size=7),
    ))

    # Línea: IPC mensual (referencia)
    fig.add_trace(go.Scatter(
        x=labels, y=m["ipc_pct"].tolist(),
        mode="lines",
        name="IPC mensual",
        line=dict(color="#f39c12", width=2, dash="dot"),
    ))

    # Anotar spread para cada mes
    for _, row in m.iterrows():
        color = "#27ae60" if row.gana_pesos else "#e74c3c"
        sign  = "+" if row.spread_pct >= 0 else ""
        fig.add_annotation(
            x=row.mes_label,
            y=max(row.tamar_tem_pct, row.be_nominal_pct) + 0.12,
            text=f"{sign}{row.spread_pct:.2f}pp",
            showarrow=False,
            font=dict(size=10, color=color),
        )

    fig.update_layout(
        yaxis_title="% mensual",
        yaxis_ticksuffix="%",
        xaxis_title="Mes",
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    )
    return _fig_to_html(fig, 460)


# ── gráfico 4: tasa real implícita en pesos ──────────────────────────────────

def chart_real_rate(m: pd.DataFrame) -> str:
    labels = m["mes_label"].tolist()
    fig = go.Figure()

    colors = ["#27ae60" if v > 0 else "#e74c3c" for v in m["tasa_real_pesos"]]

    fig.add_trace(go.Bar(
        x=labels,
        y=m["tasa_real_pesos"],
        name="Tasa real pesos (TAMAR − inflación)",
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in m["tasa_real_pesos"]],
        textposition="outside",
        textfont=dict(size=11),
    ))

    fig.add_hline(y=0, line_dash="solid", line_color="#2c3e50", line_width=1)

    fig.update_layout(
        yaxis_title="% mensual real",
        yaxis_ticksuffix="%",
        xaxis_title="Mes",
        showlegend=False,
        yaxis_autorange=True,
    )
    return _fig_to_html(fig, 320)


# ── gráfico 5: evolución histórica de expectativas ───────────────────────────

def chart_historico(df_hist: pd.DataFrame) -> str:
    fig = go.Figure()

    SERIES = [
        ("ipc_12m",   "IPC próx. 12m (% i.a.)",    "#e67e22"),
        ("tamar_12m", "TAMAR próx. 12m (TNA %)",     "#27ae60"),
        ("tc_2026",   "TC dic-2026 (ARS/USD)",        "#2980b9"),
    ]

    for var, label, color in SERIES:
        sub = df_hist[(df_hist.variable == var) & (df_hist.stat == "mediana")].sort_values("survey_date")
        if sub.empty:
            continue

        # Normalizar TC a eje derecho
        yaxis = "y2" if var == "tc_2026" else "y"

        fig.add_trace(go.Scatter(
            x=sub["survey_date"].tolist(),
            y=sub["valor"].tolist(),
            mode="lines",
            name=label,
            line=dict(color=color, width=2),
            yaxis=yaxis,
        ))

    fig.update_layout(
        yaxis=dict(title="% anual", ticksuffix="%"),
        yaxis2=dict(
            title="ARS/USD",
            overlaying="y",
            side="right",
            tickformat=",",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Fecha de encuesta"),
    )
    return _fig_to_html(fig, 380)


# ── tabla resumen ─────────────────────────────────────────────────────────────

def _badge(gana_pesos: bool, spread: float) -> str:
    if abs(spread) < 0.1:
        return '<span class="badge badge-orange">Neutro</span>'
    if gana_pesos:
        return '<span class="badge badge-green">✓ Pesos</span>'
    return '<span class="badge badge-red">✗ USD</span>'


def build_table(m: pd.DataFrame) -> str:
    rows_html = ""
    for _, row in m.iterrows():
        bg = "#f0faf4" if row.gana_pesos else "#fff5f5"
        sign = "+" if row.spread_pct >= 0 else ""
        rows_html += f"""
<tr style="background:{bg}">
  <td><strong>{row.mes_label}</strong></td>
  <td>{row.ipc_pct:.2f}%</td>
  <td>{row.tamar_tem_pct:.2f}%&nbsp;<span style="font-size:11px;color:#7f8c8d">({row.tamar_tem_pct*12:.1f}% TNA)</span></td>
  <td>{row.devaluation_pct:.2f}%</td>
  <td>{row.be_nominal_pct:.2f}%</td>
  <td>{row.be_real_pct:.3f}%</td>
  <td style="font-weight:700;color:{'#27ae60' if row.gana_pesos else '#e74c3c'}">{sign}{row.spread_pct:.2f}pp</td>
  <td>{_badge(row.gana_pesos, row.spread_pct)}</td>
</tr>"""

    return f"""
<div class="tbl-wrap">
<table class="tbl">
<thead>
<tr>
  <th>Mes</th>
  <th>IPC mensual</th>
  <th>TAMAR (TEM)</th>
  <th>Devaluación</th>
  <th>Break-even nominal</th>
  <th>Break-even real</th>
  <th>Spread (pesos−BE)</th>
  <th>Conviene</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
"""


# ── KPIs ─────────────────────────────────────────────────────────────────────

def build_kpis(m: pd.DataFrame, slug: str) -> str:
    avg_ipc  = m["ipc_pct"].mean()
    avg_dev  = m["devaluation_pct"].mean()
    avg_tamar= m["tamar_tem_pct"].mean() * 12  # TNA promedio
    n_pesos  = m["gana_pesos"].sum()
    n_total  = len(m)
    color_pesos = "green" if n_pesos > n_total / 2 else "red"

    return f"""
<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-val orange">{avg_ipc:.2f}%</div>
    <div class="kpi-label">IPC mensual promedio</div>
    <div class="kpi-sub">Mediana de la encuesta</div>
  </div>
  <div class="kpi">
    <div class="kpi-val" style="color:#2980b9">{avg_dev:.2f}%</div>
    <div class="kpi-label">Devaluación mensual promedio</div>
    <div class="kpi-sub">Implícita del forward TC</div>
  </div>
  <div class="kpi">
    <div class="kpi-val green">{avg_tamar:.1f}%</div>
    <div class="kpi-label">TAMAR promedio (TNA)</div>
    <div class="kpi-sub">Tasa de referencia en pesos</div>
  </div>
  <div class="kpi">
    <div class="kpi-val {color_pesos}">{n_pesos}/{n_total}</div>
    <div class="kpi-label">Meses donde pesos ganan</div>
    <div class="kpi-sub">Vs. mantener dólares sin rendimiento</div>
  </div>
</div>
"""


# ── ensamblado final ──────────────────────────────────────────────────────────

def build_html(df_exp: pd.DataFrame, df_hist: pd.DataFrame,
               tc_base: float, usd_yield_tna: float) -> str:
    m = compute_metrics(df_exp, tc_base, usd_yield_tna)
    slug = df_exp["survey_slug"].iloc[0]
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")

    kpis_html     = build_kpis(m, slug)
    table_html    = build_table(m)
    ch_ipc        = chart_ipc(m)
    ch_dev        = chart_devaluation(m)
    ch_be         = chart_breakeven(m, usd_yield_tna)
    ch_real       = chart_real_rate(m)
    ch_hist       = chart_historico(df_hist)

    usd_note = (f"con rendimiento USD asumido de {usd_yield_tna:.1f}% TNA"
                if usd_yield_tna > 0 else "asumiendo dólar sin rendimiento")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>REM BCRA — Análisis de Break-Even Pesos vs Dólares</title>
  <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
  <style>{_CSS}</style>
</head>
<body>
<header>
  <h1>REM BCRA — Break-Even Pesos vs Dólares</h1>
  <p>Relevamiento de Expectativas de Mercado · Encuesta {slug} · Generado: {ts}</p>
</header>
<main>

<!-- KPIs -->
{kpis_html}

<!-- explicación metodológica -->
<div class="card">
  <p class="sec-title">¿Qué muestra este reporte?</p>
  <div class="explain">
    El <strong>REM</strong> (Relevamiento de Expectativas de Mercado) del BCRA recopila mensualmente las proyecciones
    de 46 analistas locales e internacionales sobre inflación, tipo de cambio y tasas de interés.<br><br>
    Este análisis compara dos estrategias para los próximos meses:<br>
    &nbsp;&nbsp;• <strong>Invertir en pesos</strong>: depósito a plazo fijo o instrumento similar a la tasa TAMAR (TNA anual ÷ 12 = TEM mensual).<br>
    &nbsp;&nbsp;• <strong>Mantener dólares</strong>: no hay rendimiento en USD ({usd_note}).<br><br>
    <strong>Break-even nominal</strong>: la TEM en pesos que iguala el retorno de mantener dólares = devaluación mensual esperada.<br>
    <strong>Break-even real</strong>: el mismo umbral deflactado por la inflación esperada = devaluación real implícita.<br>
    <strong>Spread</strong>: TAMAR TEM − Break-even nominal. Positivo → pesos ganan; negativo → dólares ganan.
  </div>
  <div class="warn-box">
    ⚠ Este análisis compara pesos (TAMAR) vs dólares sin rendimiento.
    Para comparar con bonos hard dollar (TIR USD ~5-8%), aumentá el rendimiento USD con <code>--usd-yield 6</code>.
    El TC base usado para el primer mes es {tc_base:,.0f} ARS/USD (estimado al momento de la encuesta).
  </div>
</div>

<!-- Tabla resumen -->
<div class="card">
  <p class="sec-title">Resumen mensual</p>
  {table_html}
</div>

<!-- Break-even (chart principal) -->
<div class="card">
  <p class="sec-title">Break-even: TAMAR vs Devaluación mes a mes</p>
  <div class="explain">
    Cuando la línea verde (TAMAR TEM) está <strong>sobre</strong> la línea roja (break-even),
    los pesos rinden más que los dólares ese mes. Las anotaciones muestran el spread en puntos porcentuales.
  </div>
  {ch_be}
</div>

<!-- Inflación y devaluación -->
<div class="card">
  <p class="sec-title">Inflación y devaluación esperadas mes a mes</p>
  <p style="font-size:12px;color:#7f8c8d;margin-bottom:16px">
    Barras de error = rango intercuartil (Q25–Q75) de las respuestas del REM.
    El primer mes de devaluación usa TC base {tc_base:,.0f} ARS/USD.
  </p>
  <div class="grid2">
    <div>
      <p style="font-size:13px;font-weight:600;color:var(--navy);margin-bottom:8px">IPC mensual esperado</p>
      {ch_ipc}
    </div>
    <div>
      <p style="font-size:13px;font-weight:600;color:var(--navy);margin-bottom:8px">Devaluación mensual esperada (TC forward)</p>
      {ch_dev}
    </div>
  </div>
</div>

<!-- Tasa real en pesos -->
<div class="card">
  <p class="sec-title">Tasa real implícita en pesos (TAMAR − IPC)</p>
  <div class="explain">
    Mide si el plazo fijo en pesos supera la inflación. Barras verdes = tasa real positiva (el peso le gana a la inflación);
    rojas = tasa real negativa (la inversión en pesos pierde poder adquisitivo en términos reales).
  </div>
  {ch_real}
</div>

<!-- Histórico -->
<div class="card">
  <p class="sec-title">Evolución histórica de expectativas (REM desde 2016)</p>
  <div class="explain">
    Cómo evolucionaron los consensos del mercado sobre inflación a 12 meses, TAMAR y tipo de cambio
    a lo largo del tiempo. El TC 2026 usa el eje derecho (ARS/USD).
  </div>
  {ch_hist}
</div>

<p class="footnote">
  Fuente: Banco Central de la República Argentina (BCRA) — Relevamiento de Expectativas de Mercado ({slug}).<br>
  Tasa TAMAR: tasa de depósitos a plazo mayor de $1 MM (TNA). Se convierte a TEM = TNA/12.<br>
  Devaluación: calculada como variación % mensual del TC nominal forward (mediana de consenso).<br>
  TC base estimado: {tc_base:,.0f} ARS/USD al momento de la encuesta.<br>
  Este reporte es de carácter informativo y no constituye asesoramiento financiero.
</p>

</main>
</body>
</html>"""


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",       default=None)
    parser.add_argument("--tc-base",   type=float, default=TC_BASE_DEFAULT,
                        help=f"TC ARS/USD al momento de la encuesta (default: {TC_BASE_DEFAULT})")
    parser.add_argument("--usd-yield", type=float, default=0.0,
                        help="TNA en USD asumida para bono de referencia en dólares (default: 0%)")
    args = parser.parse_args()

    exp_path  = OUT_DIR / "rem_expectativas.parquet"
    hist_path = OUT_DIR / "rem_historico.parquet"

    for p in [exp_path, hist_path]:
        if not p.exists():
            raise FileNotFoundError(f"No se encontró {p}\nCorré primero: python fetch_rem.py")

    print("Cargando datos...")
    df_exp  = pd.read_parquet(exp_path)
    df_hist = pd.read_parquet(hist_path)
    print(f"  Expectativas: {len(df_exp)} filas | Histórico: {df_hist['survey_date'].nunique()} encuestas")

    print("Generando reporte...")
    html = build_html(df_exp, df_hist, args.tc_base, args.usd_yield)

    out = Path(args.out) if args.out else OUT_DIR / "rem_report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Reporte guardado: {out}  ({out.stat().st_size / 1024:.1f} KB)")

    docs = ROOT / "docs" / "rem_report.html"
    if docs.parent.exists():
        import shutil
        shutil.copy2(out, docs)
        print(f"Copiado a:        {docs}")
