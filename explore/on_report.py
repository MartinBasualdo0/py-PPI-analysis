"""
Pipeline completo + generación de reporte HTML para obligaciones negociables candidatas.

Uso standalone:
    python on_report.py          # usa los filtros definidos en CONFIGURACIÓN abajo
    python on_report.py --min-tir 7 --max-tir 10   # override puntual vía CLI
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN — editá estos valores para cambiar el filtro por defecto
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MIN_TIR = 7.0          # TIR mínima (%)
DEFAULT_MAX_TIR = 10.0         # TIR máxima (%)
DEFAULT_MIN_VTO = "2027-01-01"  # Vencimiento mínimo YYYY-MM-DD
# Vencimiento máximo YYYY-MM-DD (None = sin límite)
DEFAULT_MAX_VTO = None
DEFAULT_MIN_VOLUMEN = 0.0          # Volumen mínimo operado (0 = sin filtro)
DEFAULT_COTIZACION = "USD MEP"    # "ARS" | "USD MEP" | "USD CCL" | "" (todas)


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

KEY_ACCOUNTS = {
    "8000015": "deuda_fin_sobre_ebitda",
    "8000016": "ebitda_sobre_intereses",
    "8000006": "liquidez",
    "8000004": "ebitda",
    "2311600": "on_emitidas",
    "2322200": "pas_fin_corriente",
    "2312300": "pas_fin_no_corriente",
    "1122500": "efectivo",
    "2299999": "patrimonio_neto",
    "1999999": "total_activo",
    "2399999": "total_pasivo",
}

SUFFIX_TOKENS = {
    "ON", "SA", "SAS", "SAU", "SACIFI", "SACIF", "SACIFIA", "SAIC", "SAICF", "SAICFA", "SAICFIA",
    "SAICA", "SRL", "SCA", "SH", "CIASA", "CIA", "CIASAU",
    "AGICI", "AGICIYF", "AGI", "AGIC",
    "SOCIEDAD", "ANONIMA", "COMERCIAL", "INDUSTRIAL", "FINANCIERA",
    "DE", "DEL", "LA", "LAS", "LOS", "EL", "Y",
}

MARKET_ALIASES: dict[str, str] = {
    # Energía / Oil & Gas
    "TGS": "TRANSPORTADORA GAS SUR",
    "TGN": "TRANSPORTADORA GAS NORTE",
    "TRANSPORTADORA GAS DEL SUR": "TRANSPORTADORA GAS SUR",
    "TRANSPORTADORA GAS DEL NORTE": "TRANSPORTADORA GAS NORTE",
    "PAMPA ENERGIA": "PAMPA ENERGIA",
    "PAMPA": "PAMPA ENERGIA",
    "YPF LUZ": "YPF ENERGIA ELECTRICA",
    "YPF ENERGIA ELECTRICA": "YPF ENERGIA ELECTRICA",
    "YPF ENERGIA": "YPF ENERGIA ELECTRICA",
    "YPF": "YPF",
    "VISTA ENERGY ARGENTINA": "VISTA ENERGY ARGENTINA",
    "VISTA OIL & GAS": "VISTA ENERGY ARGENTINA",
    "VISTA OIL": "VISTA ENERGY ARGENTINA",
    "VISTA": "VISTA ENERGY ARGENTINA",
    "AES ARGENTINA GENERACION": "AES ARGENTINA GENERACION",
    "AES ARGENTINA": "AES ARGENTINA GENERACION",
    "AES": "AES ARGENTINA GENERACION",
    "PETROLEOS SUDAMERICANOS": "PETROLEOS SUDAMERICANOS",
    "PETROLERA ACONCAGUA": "PETROLERA ACONCAGUA ENERGIA",
    "PAN AMERICAN ENERGY": "PAN AMERICAN ENERGY",
    "CGC": "GENERAL COMBUSTIBLES",
    "COMPANIA GENERAL DE COMBUSTIBLES": "GENERAL COMBUSTIBLES",
    "GENERAL DE COMBUSTIBLES": "GENERAL COMBUSTIBLES",
    "GENNEIA": "GENNEIA",
    "GENERACION MEDITERRANEA": "GENERACION MEDITERRANEA",
    "MSU ENERGY": "MSU ENERGY",
    "MSU GREEN ENERGY": "MSU GREEN ENERGY",
    "MSU": "MSU",
    "360 ENERGY": "360 ENERGY SOLAR",
    "360 ENER SOL": "360 ENERGY SOLAR",
    "360 ENER": "360 ENERGY SOLAR",
    "CAPEX": "CAPEX",
    "CENTRAL PUERTO": "CENTRAL PUERTO",
    "CENTRAL COSTANERA": "CENTRAL COSTANERA",
    "EDENOR": "EMPRESA DISTRIBUIDORA COMERCIALIZADORA NORTE",
    "EMPRESA DISTRIBUIDORA NORTE": "EMPRESA DISTRIBUIDORA COMERCIALIZADORA NORTE",
    "METROGAS": "METROGAS",
    "ALBANESI ENERGIA": "GENERACION MEDITERRANEA",
    "ALBANESI": "GENERACION MEDITERRANEA",
    # Industria / Consumo
    "ALUAR ALUMINIO ARGENTINO": "ALUAR ALUMINIO ARGENTINO",
    "ALUAR": "ALUAR ALUMINIO ARGENTINO",
    "ARCOR": "ARCOR",
    "MASTELLONE": "MASTELLONE HERMANOS",
    "LOMA NEGRA": "LOMA NEGRA",
    "MOLINOS RIO DE LA PLATA": "MOLINOS RIO PLATA",
    "MOLINOS AGRO": "MOLINOS AGRO",
    "MOLINOS": "MOLINOS AGRO",
    "FERRUM": "FERRUM CERAMICA METALURGIA",
    "RICHMOND": "LABORATORIOS RICHMOND",
    "BOLDT": "BOLDT",
    # Agro / Real estate
    "CRESUD": "CRESUD",
    "IRSA PROPIEDADES COMERCIALES": "IRSA PROPIEDADES COMERCIALES",
    "IRSA PROPIEDADES": "IRSA PROPIEDADES COMERCIALES",
    "IRSA INVERSIONES": "IRSA INVERSIONES REPRESENTACIONES",
    "IRSA": "IRSA INVERSIONES REPRESENTACIONES",
    "RAGHSA": "RAGHSA",
    "SAN MIGUEL": "SAN MIGUEL",
    # Telecom / media
    "TELECOM ARGENTINA": "TELECOM ARGENTINA",
    "TELECOM ARG": "TELECOM ARGENTINA",
    "TELECOM": "TELECOM ARGENTINA",
    "CABLEVISION": "CABLEVISION HOLDING",
    # Bancos
    "BANCO MACRO": "BANCO MACRO",
    "BANCO HIPOTECARIO": "BANCO HIPOTECARIO",
    "BANCO SUPERVIELLE": "BANCO SUPERVIELLE",
    "BANCO SANTANDER ARGENTINA": "BANCO SANTANDER ARGENTINA",
    "BANCO SANTANDER": "BANCO SANTANDER ARGENTINA",
    "BANCO COMAFI": "BANCO COMAFI",
    "BANCO BBVA ARGENTINA": "BANCO BBVA ARGENTINA",
    "BANCO BBVA": "BANCO BBVA ARGENTINA",
    "BBVA BANCO FRANCES": "BANCO BBVA ARGENTINA",
    "BBVA": "BANCO BBVA ARGENTINA",
    "BANCO PIANO": "BANCO PIANO",
    "BANCO MARIVA": "BANCO MARIVA",
    "BANCO GALICIA Y BUENOS AIRES": "BANCO GALICIA BUENOS AIRES",
    "BANCO GALICIA": "BANCO GALICIA BUENOS AIRES",
    "GRUPO FINANCIERO GALICIA": "GRUPO FINANCIERO GALICIA",
    "GALICIA": "GRUPO FINANCIERO GALICIA",
    # Distribuidoras / tickers de mercado no obvios
    "EDEMSA": "EMP DISTRIBUIDORA ELECTRICIDAD MENDOZA",
    "PETROQUIMICA COMODORO": "PETROQUIMICA COMODORO RIVADAVIA",
    "PETROQUIMICA": "PETROQUIMICA COMODORO RIVADAVIA",
    "GMCTR": "GENERACION MEDITERRANEA",
    "AA2000": "AEROPUERTOS ARGENTINA 2000",
    "AEROP ARG 2000": "AEROPUERTOS ARGENTINA 2000",
    "AEROPUERTOS ARGENTINA 2000": "AEROPUERTOS ARGENTINA 2000",
    "SIDERSA": "SIDERSA",
    "OILTANKING EBYTEM": "OILTANKING EBYTEM",
    "RIZOBACTER": "RIZOBACTER ARGENTINA",
    "INVERSIONES JURAMENTO": "INVERSORA JURAMENTO",
    "INV JURAMENTO": "INVERSORA JURAMENTO",
    "PLAZA LOGISTICA": "PLAZA LOGISTICA",
    "LIPSA": "LIPSA",
    "CAMUZZI": "CAMUZZI GAS PAMPEANA",
    "EDESA": "EDESA HOLDING",
    "PCR": "PETROQUIMICA COMODORO RIVADAVIA",
    "GENERA LITORAL": "GENERACION LITORAL",
    "GENERACION LITORAL": "GENERACION LITORAL",
}


def _parse_amount(s) -> float | pd.NAType:
    if s is None or pd.isna(s) or str(s).strip() in {"-", ""}:
        return pd.NA
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return pd.NA


def build_company_metrics(balances: pd.DataFrame) -> pd.DataFrame:
    """CNV balance data → métricas por empresa (deuda/EBITDA, cobertura, liquidez, etc.)."""
    bal = balances.copy()
    bal["account_number"] = bal["account_number"].astype(
        str).str.strip().str.split(".").str[0]
    bal = bal[bal["account_number"].isin(
        KEY_ACCOUNTS) & bal["company"].notna()].copy()
    bal["value"] = bal["ammount"].map(_parse_amount)
    bal = bal.dropna(subset=["value"])

    # Preferimos CONSOLIDADO sobre INDIVIDUAL; dentro de eso, cierre más reciente.
    bal["_consol_rank"] = (bal["tipo_balance"] == "CONSOLIDADO").astype(int)
    bal = bal.sort_values(
        ["company", "account_number", "close_date", "_consol_rank"],
        ascending=[True, True, False, False],
    )

    anual = bal[bal["periodicity"].astype(str).isin(
        ["1", "ANUAL"])].drop_duplicates(["company", "account_number"])
    ultimo = bal.drop_duplicates(["company", "account_number"])

    anual_piv = anual.pivot_table(index="company", columns="account_number",
                                  values="value", aggfunc="first").rename(columns=KEY_ACCOUNTS)
    ultimo_piv = ultimo.pivot_table(index="company", columns="account_number",
                                    values="value", aggfunc="first").rename(columns=KEY_ACCOUNTS)

    ref_date_anual = anual.drop_duplicates("company").set_index(
        "company")["close_date"].rename("fecha_balance_anual")
    ref_date_ultimo = ultimo.drop_duplicates("company").set_index(
        "company")["close_date"].rename("fecha_balance_ultimo")
    ref_period_ultimo = ultimo.drop_duplicates("company").set_index("company")[
        "periodicity"].rename("period_ultimo")

    metrics = pd.DataFrame(index=ultimo_piv.index)
    metrics["deuda_fin_sobre_ebitda"] = anual_piv["deuda_fin_sobre_ebitda"].combine_first(
        ultimo_piv.get("deuda_fin_sobre_ebitda")
    )
    metrics["deuda_ebitda_es_anual"] = anual_piv["deuda_fin_sobre_ebitda"].notna()

    for col in ["ebitda_sobre_intereses", "liquidez", "ebitda", "on_emitidas",
                "pas_fin_corriente", "pas_fin_no_corriente", "efectivo",
                "patrimonio_neto", "total_activo", "total_pasivo"]:
        if col in ultimo_piv.columns:
            metrics[col] = ultimo_piv[col]

    metrics["deuda_fin_total"] = metrics[["pas_fin_corriente",
                                          "pas_fin_no_corriente"]].sum(axis=1, min_count=1)
    metrics = metrics.join(ref_date_anual).join(
        ref_date_ultimo).join(ref_period_ultimo)
    return metrics


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = _strip_accents(s).upper()
    s = re.sub(r"\b(?:[A-Z]\.){2,}", lambda m: m.group(0).replace(".", ""), s)
    s = re.sub(r"[\.,;:'\"`´\(\)\[\]/\\]", " ", s)
    s = re.sub(r"[^A-Z0-9& ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(p for p in s.split() if p not in SUFFIX_TOKENS and len(p) > 1)


def _find_company(desc: str, company_keys: dict[str, str], aliases: dict[str, str]) -> tuple[str | None, str]:
    n = _normalize_name(desc)
    if not n:
        return None, "empty"

    for alias, target in sorted(aliases.items(), key=lambda x: -len(x[0])):
        if n == alias or n.startswith(alias + " "):
            exact = [orig for orig, key in company_keys.items()
                     if key == target]
            if exact:
                return exact[0], f"alias_exact:{alias}"
            prefix = [orig for orig, key in company_keys.items(
            ) if key and key.startswith(target + " ")]
            if prefix:
                return min(prefix, key=lambda o: len(company_keys[o])), f"alias_prefix:{alias}"
            sub = [orig for orig, key in company_keys.items(
            ) if key and target.startswith(key + " ")]
            if sub:
                return max(sub, key=lambda o: len(company_keys[o])), f"alias_sub:{alias}"

    candidates = [(orig, key) for orig, key in company_keys.items()
                  if key and (n.startswith(key + " ") or n == key)]
    if candidates:
        best = max(candidates, key=lambda x: len(x[1]))
        return best[0], f"prefix:{best[1]}"

    desc_tokens = set(n.split()[:3])
    best, best_score = None, 0
    for orig, key in company_keys.items():
        if not key:
            continue
        score = len(desc_tokens & set(key.split()[:3]))
        if score > best_score:
            best, best_score = orig, score
    if best_score >= 2:
        return best, f"tokens:{best_score}"
    return None, "no_match"


def match_ons(ons: pd.DataFrame, company_metrics: pd.DataFrame) -> pd.DataFrame:
    """Cruza cada ON con su empresa en CNV por nombre normalizado + aliases."""
    company_keys = {c: _normalize_name(c) for c in company_metrics.index}
    result = ons["descripcion"].apply(
        lambda d: pd.Series(_find_company(d, company_keys, MARKET_ALIASES), index=[
                            "company", "match_method"])
    )
    matched = pd.concat([ons, result], axis=1)
    n = matched["company"].notna().sum()
    print(f"Matching: {n}/{len(matched)} ONs ({100*n/len(matched):.1f}%)")
    return matched


def _risk_bucket(x) -> str:
    if pd.isna(x):
        return "sin dato"
    if x < 0:
        return "EBITDA negativo"
    if x <= 2:
        return "bajo (≤2x)"
    if x <= 4:
        return "moderado (2-4x)"
    if x <= 6:
        return "alto (4-6x)"
    return "muy alto (>6x)"


def build_risk(ons_matched: pd.DataFrame, company_metrics: pd.DataFrame) -> pd.DataFrame:
    """Une ONs matcheadas con métricas financieras y agrega el bucket de riesgo."""
    risk = ons_matched.merge(
        company_metrics, left_on="company", right_index=True, how="left")
    risk["riesgo_bucket"] = risk["deuda_fin_sobre_ebitda"].apply(_risk_bucket)
    return risk


def filter_candidatas(
    risk: pd.DataFrame,
    min_tir: float = DEFAULT_MIN_TIR,
    max_tir: float = DEFAULT_MAX_TIR,
    min_vto: str = DEFAULT_MIN_VTO,
    max_vto: str | None = DEFAULT_MAX_VTO,
    min_volumen: float = DEFAULT_MIN_VOLUMEN,
    excl_buckets: set[str] | None = None,
    cotizacion: str = DEFAULT_COTIZACION,
) -> pd.DataFrame:
    """Filtra ONs por TIR, rango de vencimiento, volumen mínimo y cotización."""
    if excl_buckets is None:
        excl_buckets = set()
    mask = (
        (risk["tir_pct"].between(min_tir, max_tir))
        & (risk["fechaVencimiento"] >= pd.Timestamp(min_vto))
        & (~risk["riesgo_bucket"].isin(excl_buckets))
    )
    if max_vto:
        mask &= risk["fechaVencimiento"] <= pd.Timestamp(max_vto)
    if min_volumen > 0:
        mask &= risk["volumen"].fillna(0) >= min_volumen
    if cotizacion:
        mask &= risk["moneda_cotizacion"] == cotizacion
    return risk[mask].sort_values("tir_pct", ascending=False).reset_index(drop=True)


def run_pipeline(
    tir_path: Path | str,
    bal_path: Path | str,
    min_tir: float = DEFAULT_MIN_TIR,
    max_tir: float = DEFAULT_MAX_TIR,
    min_vto: str = DEFAULT_MIN_VTO,
    max_vto: str | None = DEFAULT_MAX_VTO,
    min_volumen: float = DEFAULT_MIN_VOLUMEN,
    excl_buckets: set[str] | None = None,
    cotizacion: str = DEFAULT_COTIZACION,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pipeline completo. Devuelve (candidatas, universo_completo)."""
    tir_path, bal_path = Path(tir_path), Path(bal_path)
    print(f"Cargando {tir_path.name} y {bal_path.name}...")
    ons = pd.read_parquet(tir_path)
    balances = pd.read_pickle(bal_path)
    print(f"  {len(ons)} ONs  |  {balances['company'].nunique()} empresas CNV")

    metrics = build_company_metrics(balances)
    matched = match_ons(ons, metrics)
    risk = build_risk(matched, metrics)
    cands = filter_candidatas(
        risk, min_tir, max_tir, min_vto, max_vto, min_volumen, excl_buckets, cotizacion)
    label = f"cotización {cotizacion}" if cotizacion else "todas las cotizaciones"
    print(f"Candidatas TIR {min_tir}–{max_tir}% ({label}): {len(cands)}")
    return cands, risk


# ═══════════════════════════════════════════════════════════════════════════════
# REPORTE HTML
# ═══════════════════════════════════════════════════════════════════════════════

VN_MIN_LOCAL = 1_000    # USD — emisiones locales (fallback)
VN_MIN_REGS = 150_000  # USD — Reg S (fallback si no hay lamina_minima)


def _vn_min(row: pd.Series) -> float:
    """Lámina mínima real (de fetch_ons.py) o estimada por heurística."""
    for col in ("lamina_minima", "denominacion_minima"):
        lam = row.get(col)
        if lam is not None and not pd.isna(lam) and float(lam) > 0:
            return float(lam)
    return VN_MIN_REGS if "REGS" in str(row.get("descripcion", "")).upper() else VN_MIN_LOCAL


_BADGE: dict[str, tuple[str, str, str]] = {
    "bajo (≤2x)":      ("#27ae60", "#e8f5e9", "#1b5e20"),
    "moderado (2-4x)": ("#f39c12", "#fff8e1", "#7f4800"),
    "alto (4-6x)":     ("#e67e22", "#fff3e0", "#bf360c"),
    "muy alto (>6x)":  ("#e74c3c", "#ffebee", "#b71c1c"),
    "EBITDA negativo": ("#8e44ad", "#f3e5f5", "#4a148c"),
    "sin dato":        ("#95a5a6", "#f5f5f5", "#424242"),
}

_SECTORS: dict[str, str] = {
    "Telecom Argentina S.A.":           "Telecomunicaciones",
    "Pampa Energía S.A.":               "Energía — generación eléctrica",
    "Central Puerto":                   "Energía — generación eléctrica",
    "Pan American Energy":              "Oil & Gas",
    "OILTANKING EBYTEM SA":             "Logística de hidrocarburos",
    "AES ARGENTINA GENERACIÓN  S.A.":   "Energía — generación eléctrica",
    "ARCOR SAIC":                       "Alimentos y consumo masivo",
    "Aeropuertos Argentina 2000 S.A.":  "Infraestructura — aeropuertos",
    "Aluar Aluminio Argentino":         "Aluminio / industria pesada",
    "Mastellone Hermanos S.A.":         "Lácteos / consumo masivo",
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
nav{background:var(--navy2);padding:10px 40px;display:flex;gap:10px;flex-wrap:wrap}
nav a{color:#cde;font-size:12px;padding:4px 10px;border-radius:4px;
      border:1px solid rgba(255,255,255,.2);transition:background .2s}
nav a:hover{background:rgba(255,255,255,.15)}
main{max-width:1180px;margin:0 auto;padding:28px 20px}
.sec-title{font-size:17px;font-weight:700;color:var(--navy);margin:0 0 14px;
           padding-bottom:7px;border-bottom:2px solid var(--navy)}
.ov-table{width:100%;border-collapse:collapse;background:var(--card);border-radius:8px;
          overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:36px}
.ov-table th{background:var(--navy);color:#fff;padding:9px 11px;text-align:left;
             font-size:11px;font-weight:600;letter-spacing:.4px;text-transform:uppercase}
.ov-table td{padding:8px 11px;border-bottom:1px solid var(--border);font-size:13px}
.ov-table tr:last-child td{border-bottom:none}
.ov-table tr:hover td{background:#f8fafc}
.card{background:var(--card);border-radius:10px;padding:26px;margin-bottom:36px;
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
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.chip{display:inline-block;padding:4px 11px;border-radius:16px;font-size:11px;
      font-weight:600;border-width:1px;border-style:solid}
.narr{background:#f8fafc;border-left:3px solid var(--navy);padding:11px 15px;
      border-radius:0 6px 6px 0;font-size:13px;color:#34495e;margin-bottom:16px;line-height:1.75}
.narr strong{color:var(--navy)}
.warn{color:#e67e22}
.bad{color:#e74c3c}
.chart-wrap{border-radius:6px;overflow:hidden}
.footnote{font-size:11px;color:var(--muted);text-align:center;
          margin-top:36px;padding-top:16px;border-top:1px solid var(--border);line-height:1.8}
.filter-bar{background:var(--navy2);padding:12px 40px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.risk-legend{background:#f8f9fb;border-bottom:1px solid #dde3ec;padding:10px 40px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px}
.risk-legend-title{font-weight:600;color:#334;white-space:nowrap}
.risk-pill{border:1px solid;border-radius:12px;padding:3px 10px;font-size:11px;white-space:nowrap}
.risk-pill small{opacity:.75;margin-left:2px}
.risk-legend-hint{color:#667;font-size:11px;font-style:italic;margin-left:8px}
.filter-bar label{color:#cde;font-size:12px;display:flex;align-items:center;gap:6px}
.filter-bar input,.filter-bar select{background:#1a2f50;border:1px solid rgba(255,255,255,.25);color:#fff;border-radius:4px;padding:4px 7px;font-size:12px;width:auto}
.filter-bar input[type=number]{width:70px}
.filter-bar input[type=date]{width:130px}
.filter-bar select{width:110px}
.filter-btn{background:#27ae60;color:#fff;border:none;border-radius:5px;padding:7px 18px;font-size:13px;font-weight:600;cursor:pointer}
.filter-btn:hover{background:#219a52}
.cands-count{color:#a8ffc8;font-size:12px;font-weight:600;margin-left:8px}
"""

_JS = r"""
const ALL_ONDS = JSON.parse(document.getElementById('ons-data').textContent);
const MAX_VOL = Math.max(...ALL_ONDS.map(b => b.volumen || 0), 1);
const EXCL_BUCKETS = [];
const BADGE_COLORS = {
  "bajo (≤2x)": "#27ae60",
  "moderado (2-4x)": "#f39c12",
  "alto (4-6x)": "#e67e22",
  "muy alto (>6x)": "#e74c3c",
  "EBITDA negativo": "#8e44ad",
  "sin dato": "#95a5a6",
};
const BADGE_BG = {
  "bajo (≤2x)": "#e8f5e9",
  "moderado (2-4x)": "#fff8e1",
  "alto (4-6x)": "#fff3e0",
  "muy alto (>6x)": "#ffebee",
  "EBITDA negativo": "#f3e5f5",
  "sin dato": "#f5f5f5",
};

function applyFilters() {
  const minTir = parseFloat(document.getElementById('f-min-tir').value) || 0;
  const maxTir = parseFloat(document.getElementById('f-max-tir').value) || 100;
  const minVto = document.getElementById('f-min-vto').value || '2000-01-01';
  const maxVto = document.getElementById('f-max-vto').value || '2099-12-31';
  const cotizacion = document.getElementById('f-cotizacion').value;
  const minVol = parseFloat(document.getElementById('f-min-vol').value) || 0;

  const cands = ALL_ONDS.filter(b => {
    if (EXCL_BUCKETS.includes(b.riesgo_bucket)) return false;
    if (b.tir_pct === null || b.tir_pct < minTir || b.tir_pct > maxTir) return false;
    const vto = b.fechaVencimiento || '';
    if (vto < minVto || vto > maxVto) return false;
    if (cotizacion && b.moneda_cotizacion !== cotizacion) return false;
    if (minVol > 0 && (b.volumen === null || b.volumen < minVol)) return false;
    return true;
  });

  renderNav(cands);
  renderOverview(cands);
  updateDotPlot(cands, minTir, maxTir, minVto, maxVto);
  showHideCards(cands);

  const counter = document.getElementById('cands-counter');
  if (counter) counter.textContent = cands.length + ' candidatas';
}

function showHideCards(cands) {
  const tickerSet = new Set(cands.map(b => b.ticker));
  document.querySelectorAll('section[data-ticker]').forEach(sec => {
    sec.style.display = tickerSet.has(sec.dataset.ticker) ? '' : 'none';
  });
}

function renderNav(cands) {
  const nav = document.getElementById('cands-nav');
  if (!nav) return;
  nav.innerHTML = cands.map(b => {
    const tir = b.tir_pct !== null ? b.tir_pct.toFixed(1) : '?';
    return '<a href="#' + b.ticker + '">' + b.ticker + ' · ' + tir + '%</a>';
  }).join('');
}

function renderOverview(cands) {
  const tbody = document.getElementById('overview-tbody');
  if (!tbody) return;
  tbody.innerHTML = cands.map(b => {
    const company = (b.company || '❓ sin match').substring(0, 34);
    const bucket = b.riesgo_bucket || 'sin dato';
    const color = BADGE_COLORS[bucket] || '#95a5a6';
    const bg = BADGE_BG[bucket] || '#f5f5f5';
    const de = b.deuda_fin_sobre_ebitda !== null ? b.deuda_fin_sobre_ebitda.toFixed(2) + 'x' : 'N/D';
    const tir = b.tir_pct !== null ? b.tir_pct.toFixed(2) + '%' : '?';
    const price = b.price !== null ? b.price.toFixed(2) : '?';
    const curr = b.moneda_cotizacion === 'ARS' ? 'ARS' : 'USD';
    let vnMin = 1000;
    if (b.lamina_minima !== null && b.lamina_minima > 0) {
      vnMin = b.lamina_minima;
    } else if (b.descripcion && b.descripcion.toUpperCase().includes('REGS')) {
      vnMin = 150000;
    }
    const minInv = (b.price || 0) * (vnMin / 100);
    return '<tr>' +
      '<td><a href="#' + b.ticker + '">' + b.ticker + '</a></td>' +
      '<td>' + company + '</td>' +
      '<td><strong>' + tir + '</strong></td>' +
      '<td>' + (b.fechaVencimiento || '') + '</td>' +
      '<td>' + price + '</td>' +
      '<td><strong>~' + curr + ' ' + Math.round(minInv).toLocaleString() + '</strong></td>' +
      '<td style="background:' + bg + ';color:' + color + ';font-weight:700;font-size:11px;border-radius:4px;white-space:nowrap">' + bucket + '</td>' +
      '<td>' + de + '</td>' +
      '</tr>';
  }).join('');
}

function updateDotPlot(cands, minTir, maxTir, minVto, maxVto) {
  const div = document.getElementById('tir-dotplot');
  if (!div || !div.data) return;

  const traceIdx = div.data.findIndex(t => t.name === 'Candidatas');
  if (traceIdx === -1) return;

  const x = cands.map(b => b.fechaVencimiento);
  const y = cands.map(b => b.tir_pct);
  const text = cands.map(b => b.ticker);
  const colors = cands.map(b => BADGE_COLORS[b.riesgo_bucket] || '#95a5a6');
  const sizes = cands.map(b => 10 + 24 * Math.sqrt((b.volumen || 0) / MAX_VOL));
  const customdata = cands.map(b => [b.ticker, b.company || '', b.price || 0, b.volumen || 0, b.moneda_cotizacion || '']);

  Plotly.restyle(div, {
    x: [x], y: [y], text: [text],
    'marker.color': [colors], 'marker.size': [sizes], customdata: [customdata],
  }, traceIdx);

  // Actualizar el rectángulo sombreado y la anotación con los nuevos filtros
  const maxVtoDate = ALL_ONDS.reduce((m, b) => b.fechaVencimiento > m ? b.fechaVencimiento : m, '2000-01-01');
  const x1 = (maxVto && maxVto < '2099-12-31') ? maxVto : maxVtoDate;
  const label = maxVto && maxVto < '2099-12-31'
    ? 'TIR ' + minTir + '–' + maxTir + '%  ·  vto ' + minVto.slice(0,7) + '–' + maxVto.slice(0,7)
    : 'TIR ' + minTir + '–' + maxTir + '%  ·  vto ≥ ' + minVto.slice(0,7);
  Plotly.relayout(div, {
    'shapes[0].y0': minTir,
    'shapes[0].y1': maxTir,
    'shapes[0].x0': minVto,
    'shapes[0].x1': x1,
    'annotations[0].y': maxTir,
    'annotations[0].text': label,
  });
}

window.addEventListener('load', applyFilters);
"""


def _ons_to_json(df: pd.DataFrame) -> str:
    """Serializa columnas clave del DataFrame a JSON embebible en HTML."""
    cols = [
        "ticker", "descripcion", "company", "moneda_cotizacion", "moneda_emision",
        "tir_pct", "fechaVencimiento", "volumen", "price", "riesgo_bucket",
        "deuda_fin_sobre_ebitda", "lamina_minima",
    ]
    # Solo columnas que existen
    present = [c for c in cols if c in df.columns]
    sub = df[present].copy()

    # Convertir fechas a string ISO YYYY-MM-DD
    for col in sub.columns:
        if pd.api.types.is_datetime64_any_dtype(sub[col]):
            sub[col] = sub[col].dt.strftime("%Y-%m-%d")
            sub[col] = sub[col].where(sub[col].notna(), None)

    records = []
    for _, row in sub.iterrows():
        rec = {}
        for col in present:
            val = row[col]
            if val is None:
                rec[col] = None
            elif isinstance(val, float) and (val != val):  # NaN check
                rec[col] = None
            elif hasattr(val, 'item'):  # numpy scalar
                v = val.item()
                rec[col] = None if isinstance(v, float) and (v != v) else v
            elif isinstance(val, pd.NaT.__class__):
                rec[col] = None
            else:
                try:
                    import math
                    if isinstance(val, float) and math.isnan(val):
                        rec[col] = None
                    else:
                        rec[col] = val
                except (TypeError, ValueError):
                    rec[col] = val
        records.append(rec)

    return json.dumps(records, ensure_ascii=False, default=str)


def _filter_bar_html(
    min_tir: float,
    max_tir: float,
    min_vto: str,
    max_vto: str | None,
    min_volumen: float,
    cotizacion: str,
) -> str:
    max_vto_val = max_vto or ""
    cotiz_options = ""
    for opt in ["", "USD MEP", "USD CCL", "ARS"]:
        selected = ' selected' if opt == cotizacion else ''
        label = opt if opt else "Todas"
        cotiz_options += f'<option value="{opt}"{selected}>{label}</option>'

    return f"""<div class="filter-bar">
  <label>TIR mín. <input type="number" id="f-min-tir" value="{min_tir}" step="0.5" min="0" max="100"></label>
  <label>TIR máx. <input type="number" id="f-max-tir" value="{max_tir}" step="0.5" min="0" max="100"></label>
  <label>Vto desde <input type="date" id="f-min-vto" value="{min_vto}"></label>
  <label>Vto hasta <input type="date" id="f-max-vto" value="{max_vto_val}"></label>
  <label>Cotización <select id="f-cotizacion">{cotiz_options}</select></label>
  <label>Vol. mín. <input type="number" id="f-min-vol" value="{min_volumen}" step="1000" min="0"></label>
  <button class="filter-btn" onclick="applyFilters()">Aplicar filtros</button>
  <span class="cands-count" id="cands-counter">— candidatas</span>
</div>"""


def _parse_flujos(flujos_raw) -> pd.DataFrame:
    raw = json.loads(flujos_raw) if isinstance(
        flujos_raw, str) else (flujos_raw or [])
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
        rows.append({
            "fecha":        fecha,
            "amortizacion": float(f.get("amortizacion") or 0),
            "interes":      float(f.get("interes") or f.get("renta") or 0),
            "total":        float(f.get("total") or 0),
        })
    if not rows:
        return pd.DataFrame(columns=["fecha", "amortizacion", "interes", "total"])
    fl = pd.DataFrame(rows).sort_values("fecha").reset_index(drop=True)
    # Descartar fechas donde la API no devolvió montos (datos incompletos del leg ARS)
    fl = fl[fl["total"] > 0].reset_index(drop=True)
    return fl


def _chip(text: str, border: str, bg: str, color: str) -> str:
    return f'<span class="chip" style="background:{bg};color:{color};border-color:{border}">{text}</span>'


def _row_html(k: str, v: str) -> str:
    return f"<tr><td>{k}</td><td>{v}</td></tr>"


def _risk_chips(row: pd.Series) -> str:
    bucket = str(row.get("riesgo_bucket", "sin dato"))
    chips = [_chip(f"Riesgo: {bucket}", *
                   _BADGE.get(bucket, _BADGE["sin dato"]))]

    d_e = row.get("deuda_fin_sobre_ebitda")
    if pd.notna(d_e):
        tier = "bajo (≤2x)" if d_e <= 2 else "moderado (2-4x)" if d_e <= 4 else "alto (4-6x)" if d_e <= 6 else "muy alto (>6x)"
        chips.append(_chip(f"D/EBITDA: {d_e:.1f}x", *_BADGE[tier]))

    e_i = row.get("ebitda_sobre_intereses")
    if pd.notna(e_i):
        cov = abs(e_i)
        tier = "bajo (≤2x)" if cov >= 4 else "moderado (2-4x)" if cov >= 2.5 else "alto (4-6x)" if cov >= 1.5 else "muy alto (>6x)"
        chips.append(_chip(f"Cobertura int.: {cov:.1f}x", *_BADGE[tier]))

    liq = row.get("liquidez")
    if pd.notna(liq):
        tier = "bajo (≤2x)" if liq >= 1.5 else "moderado (2-4x)" if liq >= 1.0 else "muy alto (>6x)"
        chips.append(_chip(f"Liquidez: {liq:.2f}", *_BADGE[tier]))

    return '<div class="chips">' + "".join(chips) + "</div>"


def _narrative(row: pd.Series) -> str:
    company = str(row.get("company") or "El emisor")
    d_e = row.get("deuda_fin_sobre_ebitda")
    e_i = row.get("ebitda_sobre_intereses")
    liq = row.get("liquidez")

    if pd.isna(d_e):
        return (
            "<strong>Sin datos de balance CNV disponibles.</strong> "
            "Este emisor no fue cruzado con los balances reportados a la CNV. "
            "Se recomienda revisar los estados financieros en la web de la CNV o en el "
            "prospecto antes de invertir."
        )

    anual = "anual ✓" if row.get("deuda_ebitda_es_anual") else "trimestral ⚠"
    parts = []

    if d_e < 0:
        parts.append(
            f'<strong class="bad">{company} presenta EBITDA negativo</strong>: la empresa no genera '
            "suficiente resultado operativo, lo que impide calcular el ratio de apalancamiento de forma significativa."
        )
    elif d_e <= 2:
        parts.append(
            f"<strong>{company}</strong> tiene un apalancamiento bajo ({d_e:.1f}x Deuda/EBITDA, balance {anual}), "
            "con una estructura financiera sólida y amplia capacidad de repago."
        )
    elif d_e <= 3.5:
        parts.append(
            f"<strong>{company}</strong> opera con apalancamiento moderado ({d_e:.1f}x Deuda/EBITDA, {anual}), "
            "dentro de rangos razonables para el sector. No hay indicadores de estrés financiero inmediato."
        )
    elif d_e <= 5:
        parts.append(
            f'<strong class="warn">{company}</strong> tiene un leverage moderadamente elevado '
            f"({d_e:.1f}x Deuda/EBITDA, {anual}). Conviene monitorear la evolución del EBITDA y el perfil de vencimientos."
        )
    else:
        parts.append(
            f'<strong class="bad">{company}</strong> presenta apalancamiento alto ({d_e:.1f}x Deuda/EBITDA, {anual}), '
            "lo que eleva el riesgo crediticio. Ante caídas del EBITDA o necesidad de refinanciar, "
            "la empresa podría enfrentar dificultades."
        )

    if pd.notna(e_i):
        cov = abs(e_i)
        if cov >= 4:
            parts.append(
                f"La cobertura de intereses es excelente ({cov:.1f}x EBITDA/Intereses): "
                "el flujo operativo supera ampliamente los costos financieros."
            )
        elif cov >= 2.5:
            parts.append(
                f"La cobertura de intereses es adecuada ({cov:.1f}x), con margen razonable sobre los compromisos de deuda.")
        elif cov >= 1.5:
            parts.append(
                f'<span class="warn">La cobertura de intereses es ajustada ({cov:.1f}x):</span> '
                "el EBITDA cubre los intereses pero con poco margen ante caídas en resultados."
            )
        else:
            parts.append(
                f'<strong class="bad">Cobertura de intereses crítica ({cov:.1f}x):</strong> '
                "el EBITDA apenas alcanza para cubrir los gastos financieros. Señal de alerta."
            )

    if pd.notna(liq):
        if liq >= 1.5:
            parts.append(
                f"La liquidez corriente ({liq:.2f}) es buena; activos de corto plazo cubren holgadamente los pasivos corrientes.")
        elif liq >= 1.0:
            parts.append(
                f"La liquidez corriente ({liq:.2f}) es ajustada pero positiva.")
        else:
            parts.append(
                f'<strong class="bad">Liquidez corriente baja ({liq:.2f}):</strong> '
                "los pasivos corrientes superan a los activos de corto plazo — posible presión de caja en el corto plazo."
            )

    return " ".join(parts)


def _payment_chart(row: pd.Series) -> str:
    fl = _parse_flujos(row["flujos"])
    if fl.empty:
        return "<p style='color:gray;padding:12px'>Sin flujos futuros disponibles.</p>"

    has_bd = (fl["amortizacion"] > 0).any() or (fl["interes"] > 0).any()
    total_usd = (fl["amortizacion"] + fl["interes"]
                 if has_bd else fl["total"]).sum()

    fig = go.Figure()
    if has_bd:
        fig.add_trace(go.Bar(
            name="Intereses", x=fl["fecha"], y=fl["interes"], marker_color="#4472CA",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Interés: <b>%{y:.4f}</b> / 100 VN<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="Amortización", x=fl["fecha"], y=fl["amortizacion"], marker_color="#70AD47",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Amortización: <b>%{y:.4f}</b> / 100 VN<extra></extra>",
        ))
    else:
        fig.add_trace(go.Bar(
            name="Pago total", x=fl["fecha"], y=fl["total"], marker_color="#4472CA",
            hovertemplate="<b>%{x|%d %b %Y}</b><br>Total: <b>%{y:.4f}</b> / 100 VN<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text=f"Flujo de pagos futuros — {row['ticker']}  ·  Total restante: <b>{total_usd:.2f}</b> por c/100 VN",
            font=dict(size=12),
        ),
        barmode="stack", height=300, template="plotly_white",
        margin=dict(t=80, b=45, l=55, r=15),
        legend=dict(orientation="h", x=0.5, xanchor="center",
                    y=1.0, yanchor="bottom"),
        xaxis=dict(
            title="Fecha de pago",
            tickmode="array",
            tickvals=fl["fecha"].tolist(),
            ticktext=[d.strftime("%-d %b %Y") for d in fl["fecha"]],
            tickangle=-45,
        ),
        yaxis=dict(title="USD / 100 VN"),
        font=dict(size=11),
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False, config={"displayModeBar": False})


def _dotplot_html(
    cands: pd.DataFrame,
    ons_all: pd.DataFrame | None = None,
    min_tir: float = 7.0,
    max_tir: float = 9.0,
    min_vto: str = "2027-01-01",
    max_vto: str | None = None,
) -> str:
    """Scatter TIR vs. vencimiento: universo completo de fondo + candidatas destacadas."""
    import numpy as np

    _COTIZ_COLOR = {"ARS": "#aab4c8",
                    "USD CCL": "#f0b97a", "USD MEP": "#7dcba4"}

    fig = go.Figure()

    # ── Área sombreada del filtro ─────────────────────────────────────────────
    universe = ons_all if ons_all is not None else cands
    x_rect_max = pd.Timestamp(max_vto) if max_vto else pd.to_datetime(
        universe["fechaVencimiento"]).max()
    fig.add_shape(
        type="rect",
        x0=pd.Timestamp(min_vto), x1=x_rect_max,
        y0=min_tir, y1=max_tir,
        fillcolor="rgba(39,174,96,0.08)",
        line=dict(color="rgba(39,174,96,0.5)", width=1, dash="dash"),
        layer="below",
    )
    vto_label = f"vto {min_vto[:7]}–{max_vto[:7]}" if max_vto else f"vto ≥ {min_vto[:7]}"
    fig.add_annotation(
        x=pd.Timestamp(min_vto), y=max_tir,
        text=f"TIR {min_tir}–{max_tir}%  ·  {vto_label}",
        showarrow=False, xanchor="left", yanchor="bottom",
        font=dict(size=10, color="rgba(39,174,96,0.8)"),
    )

    # ── Universo completo (fondo, sin labels) ─────────────────────────────────
    if ons_all is not None:
        bg = ons_all.copy()
        bg["fechaVencimiento"] = pd.to_datetime(bg["fechaVencimiento"])
        cand_tickers = set(cands["ticker"])
        bg = bg[~bg["ticker"].isin(cand_tickers)]

        for cotiz, grp in bg.groupby("moneda_cotizacion"):
            cotiz_str = str(cotiz)
            fig.add_trace(go.Scatter(
                x=grp["fechaVencimiento"],
                y=grp["tir_pct"],
                mode="markers",
                name=cotiz_str,
                legendgroup=f"bg_{cotiz_str}",
                showlegend=True,
                marker=dict(
                    size=6,
                    color=_COTIZ_COLOR.get(cotiz_str, "#cccccc"),
                    opacity=0.45,
                    line=dict(width=0),
                ),
                customdata=grp[["ticker", "descripcion",
                                "moneda_cotizacion", "volumen"]].astype(str).values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b>  %{customdata[1]}<br>"
                    "TIR: %{y:.2f}%  ·  Vto: %{x|%d/%m/%Y}<br>"
                    "Cotiza en: %{customdata[2]}  ·  Vol: %{customdata[3]}<extra></extra>"
                ),
            ))

    # ── Candidatas (frente, trazo único con color por punto) ─────────────────
    df = cands.copy()
    df["fechaVencimiento"] = pd.to_datetime(df["fechaVencimiento"])
    vol = df["volumen"].fillna(0).clip(lower=0)
    vol_max = vol.max() if vol.max() > 0 else 1
    df["_size"] = 10 + 24 * np.sqrt(vol / vol_max)
    df["_color"] = df["riesgo_bucket"].map(
        lambda b: _BADGE.get(b, _BADGE["sin dato"])[0]
    )

    fig.add_trace(go.Scatter(
        x=df["fechaVencimiento"],
        y=df["tir_pct"],
        mode="markers+text",
        name="Candidatas",
        marker=dict(
            size=df["_size"].tolist(),
            color=df["_color"].tolist(),
            line=dict(width=1.5, color="white"),
            opacity=0.95,
        ),
        text=df["ticker"],
        textposition="top center",
        textfont=dict(size=10),
        customdata=df[["ticker", "company", "price",
                       "volumen", "moneda_cotizacion"]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b>  %{customdata[1]}<br>"
            "TIR: <b>%{y:.2f}%</b>  ·  Vto: %{x|%d/%m/%Y}<br>"
            "Precio: %{customdata[2]:,.0f} ARS  ·  Vol: %{customdata[3]:,.0f}<br>"
            "Cotiza en: %{customdata[4]}<extra></extra>"
        ),
    ))

    fig.update_layout(
        height=420,
        template="plotly_white",
        margin=dict(t=20, b=40, l=55, r=15),
        xaxis=dict(title="Fecha de vencimiento", tickformat="%b %Y"),
        yaxis=dict(title="TIR (%)", ticksuffix="%", range=[0, 14]),
        legend=dict(title="", orientation="v", font=dict(size=10)),
        font=dict(size=11),
        hovermode="closest",
    )
    return pio.to_html(
        fig, full_html=False, include_plotlyjs=False,
        config={"displayModeBar": False}, div_id="tir-dotplot",
    )


def _bond_card_html(row: pd.Series) -> str:
    ticker = str(row["ticker"])
    desc = str(row.get("descripcion", ""))
    company = str(row.get("company") or "Sin datos CNV")
    tir = row["tir_pct"]
    price = float(row.get("price") or 0)
    vto = str(row["fechaVencimiento"])[:10]
    cotiz = str(row.get("moneda_cotizacion", ""))
    sector = _SECTORS.get(company, "—")
    fecha_b = str(row.get("fecha_balance_ultimo", "N/D"))[:10]
    anual_f = "anual ✓" if row.get("deuda_ebitda_es_anual") else "trimestral ⚠"
    d_e = row.get("deuda_fin_sobre_ebitda")
    e_i = row.get("ebitda_sobre_intereses")
    liq = row.get("liquidez")
    vol = float(row.get("volumen") or 0)
    vn_min = _vn_min(row)
    min_inv = price * (vn_min / 100)
    curr = "ARS" if cotiz == "ARS" else "USD"

    ctbl = (
        _row_html("Empresa", company[:42]) +
        _row_html("Sector", sector) +
        _row_html("Riesgo crediticio", str(row.get("riesgo_bucket", "sin dato"))) +
        _row_html("Deuda Fin / EBITDA", f"{d_e:.2f}x ({anual_f})" if pd.notna(d_e) else "N/D") +
        _row_html("EBITDA / Intereses", f"{abs(e_i):.2f}x" if pd.notna(e_i) else "N/D") +
        _row_html("Liquidez corriente", f"{liq:.2f}" if pd.notna(liq) else "N/D") +
        _row_html("Último balance", fecha_b)
    )
    btbl = (
        _row_html("Ticker", f"<strong>{ticker}</strong>") +
        _row_html("Descripción", desc[:50] + ("…" if len(desc) > 50 else "")) +
        _row_html("Vencimiento", vto) +
        _row_html("Precio actual", f"{price:.2f}") +
        _row_html("TIR", f"<strong>{tir:.2f}%</strong>") +
        _row_html("Cotiza en", cotiz) +
        _row_html("VN mínimo estimado", f"{curr} {vn_min:,.0f} *") +
        _row_html("Inversión mínima est.", f"<strong>{curr} {min_inv:,.0f}</strong>") +
        _row_html("Volumen reciente op.", f"{vol:,.0f}")
    )

    return f"""<section class="card" id="{ticker}" data-ticker="{ticker}">
  <div class="bond-hdr">
    <span class="ticker-badge">{ticker}</span>
    <span class="bond-desc">{desc}</span>
    <span class="tir-badge">TIR {tir:.2f}%</span>
  </div>
  {_risk_chips(row)}
  <div class="grid2">
    <div>
      <table class="info-tbl">
        <thead><tr><th colspan="2">Empresa emisora</th></tr></thead>
        <tbody>{ctbl}</tbody>
      </table>
    </div>
    <div>
      <table class="info-tbl">
        <thead><tr><th colspan="2">Datos del bono</th></tr></thead>
        <tbody>{btbl}</tbody>
      </table>
    </div>
  </div>
  <div class="narr">{_narrative(row)}</div>
  <div class="chart-wrap">{_payment_chart(row)}</div>
</section>
"""


def _overview_html(cands: pd.DataFrame) -> str:
    rows_html = ""
    for _, r in cands.iterrows():
        company = str(r.get("company") or "❓ sin match")
        bucket = str(r.get("riesgo_bucket", "sin dato"))
        b, bg, tc = _BADGE.get(bucket, _BADGE["sin dato"])
        d_e = r.get("deuda_fin_sobre_ebitda")
        min_inv = float(r.get("price") or 0) * (_vn_min(r) / 100)
        curr = "ARS" if r.get("moneda_cotizacion") == "ARS" else "USD"
        rows_html += f"""<tr>
          <td><a href="#{r['ticker']}">{r['ticker']}</a></td>
          <td>{company[:34]}</td>
          <td><strong>{r['tir_pct']:.2f}%</strong></td>
          <td>{str(r['fechaVencimiento'])[:10]}</td>
          <td>{float(r.get('price') or 0):.2f}</td>
          <td><strong>~{curr} {min_inv:,.0f}</strong></td>
          <td style="background:{bg};color:{tc};font-weight:700;font-size:11px;
                     border-radius:4px;white-space:nowrap">{bucket}</td>
          <td>{f"{d_e:.2f}x" if pd.notna(d_e) else "N/D"}</td>
        </tr>"""
    return f"""
<h2 class="sec-title">Resumen de candidatas</h2>
<table class="ov-table">
  <thead><tr>
    <th>Ticker</th><th>Empresa</th><th>TIR</th><th>Vencimiento</th>
    <th>Precio</th><th>Inversión mín. est.</th><th>Riesgo</th><th>D/EBITDA</th>
  </tr></thead>
  <tbody id="overview-tbody">{rows_html}</tbody>
</table>
"""


def build_html_report(
    cands: pd.DataFrame,
    ons_all: pd.DataFrame | None = None,
    min_tir: float = DEFAULT_MIN_TIR,
    max_tir: float = DEFAULT_MAX_TIR,
    min_vto: str = DEFAULT_MIN_VTO,
    max_vto: str | None = DEFAULT_MAX_VTO,
) -> str:
    """Genera el HTML completo del reporte a partir del DataFrame de candidatas."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Determinar universo para pre-render de tarjetas ───────────────────────
    today = pd.Timestamp.now().normalize()
    if ons_all is not None:
        pre_mask = (
            ons_all["tir_pct"].between(0, 30)
            & (pd.to_datetime(ons_all["fechaVencimiento"]) >= today)
        )
        prerender_df = ons_all[pre_mask].sort_values(
            "tir_pct", ascending=False).reset_index(drop=True)
    else:
        prerender_df = cands.copy()

    n_prerender = len(prerender_df)
    print(f"Pre-renderizando {n_prerender} tarjetas de bonos...")

    # ── Nav inicial (se reescribe en JS) ─────────────────────────────────────
    nav = "".join(
        f'<a href="#{r["ticker"]}">{r["ticker"]} · {r["tir_pct"]:.1f}%</a>'
        for _, r in cands.iterrows()
    )

    # ── Todas las tarjetas pre-renderizadas ──────────────────────────────────
    sections = "".join(_bond_card_html(r) for _, r in prerender_df.iterrows())

    # ── JSON embebido con datos de todas las ONs ─────────────────────────────
    embed_df = ons_all if ons_all is not None else cands
    ons_json = _ons_to_json(embed_df)

    # ── Filter bar ───────────────────────────────────────────────────────────
    filter_bar = _filter_bar_html(
        min_tir, max_tir, min_vto, max_vto, DEFAULT_MIN_VOLUMEN, DEFAULT_COTIZACION)

    return (
        """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ONs Candidatas — TIR 7–9% — Cotización USD MEP — """
        + ts
        + """</title>
  <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
  <style>"""
        + _CSS
        + """</style>
</head>
<body>
<header>
  <h1>Obligaciones Negociables — Candidatas TIR 7–9% · Cotización USD MEP</h1>
  <p>Hard-dollar · Vencimiento posterior a enero 2027 · Riesgo crediticio visible en cada bono · Datos al """
        + ts
        + """</p>
</header>
<nav id="cands-nav">"""
        + nav
        + """</nav>"""
        + filter_bar
        + """
<div class="risk-legend">
  <span class="risk-legend-title">Riesgo crediticio (Deuda / EBITDA):</span>
  <span class="risk-pill" style="background:#e8f5e9;color:#1b5e20;border-color:#27ae60">&#9679; Bajo <small>≤ 2x</small></span>
  <span class="risk-pill" style="background:#fff8e1;color:#7f4800;border-color:#f39c12">&#9679; Moderado <small>2–4x</small></span>
  <span class="risk-pill" style="background:#fff3e0;color:#bf360c;border-color:#e67e22">&#9679; Alto <small>4–6x</small></span>
  <span class="risk-pill" style="background:#ffebee;color:#b71c1c;border-color:#e74c3c">&#9679; Muy alto <small>&gt; 6x</small></span>
  <span class="risk-pill" style="background:#f3e5f5;color:#4a148c;border-color:#8e44ad">&#9679; EBITDA negativo</span>
  <span class="risk-pill" style="background:#f5f5f5;color:#424242;border-color:#95a5a6">&#9679; Sin dato</span>
  <span class="risk-legend-hint">El ratio mide cuántos años de resultado operativo (EBITDA) se necesitan para cancelar toda la deuda financiera.</span>
</div>
<main>
  <h2 class="sec-title">Curva de TIRs</h2>
  <div class="card" style="padding:16px 20px">
    """
        + _dotplot_html(cands, ons_all, min_tir, max_tir, min_vto, max_vto)
        + """
  </div>
  """
        + _overview_html(cands)
        + """
  <h2 class="sec-title">Análisis por ON</h2>
  """
        + sections
        + """
  <p class="footnote">
    Datos de TIR y precios: PPI (Portfolio Personal Inversiones) &nbsp;·&nbsp;
    Balances: CNV (Comisión Nacional de Valores).<br>
    * Inversión mínima estimada: precio cotizado en ARS × VN mínimo (1.000 para emisiones locales,
    150.000 para Reg S / "REGS"). Verificar denominación mínima y lote mínimo con el broker antes de operar.<br>
    Este reporte es de carácter informativo y no constituye asesoramiento financiero.
  </p>
</main>
<script id="ons-data" type="application/json">"""
        + ons_json
        + """</script>
<script>"""
        + _JS
        + """</script>
</body>
</html>"""
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Genera el reporte HTML de ONs candidatas.")
    parser.add_argument("--min-tir",     type=float, default=DEFAULT_MIN_TIR)
    parser.add_argument("--max-tir",     type=float, default=DEFAULT_MAX_TIR)
    parser.add_argument("--min-vto",     type=str,   default=DEFAULT_MIN_VTO)
    parser.add_argument("--max-vto",     type=str,   default=DEFAULT_MAX_VTO)
    parser.add_argument("--min-volumen", type=float,
                        default=DEFAULT_MIN_VOLUMEN)
    parser.add_argument("--cotizacion",  type=str,   default=DEFAULT_COTIZACION,
                        help="ARS | USD MEP | USD CCL | '' (todas)")
    parser.add_argument("--out",        type=str,   default=None,
                        help="Ruta del HTML de salida")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    tir_path = root / "output" / "on_tir.parquet"
    bal_path = root / "balance_data_html.pkl"

    for p in (tir_path, bal_path):
        if not p.exists():
            raise FileNotFoundError(f"No se encontró: {p}")

    cands, ons_all = run_pipeline(
        tir_path, bal_path,
        args.min_tir, args.max_tir,
        args.min_vto, args.max_vto,
        args.min_volumen,
        cotizacion=args.cotizacion,
    )

    out = Path(args.out) if args.out else root / \
        "output" / "on_candidatas_report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        build_html_report(cands, ons_all, args.min_tir,
                          args.max_tir, args.min_vto, args.max_vto),
        encoding="utf-8",
    )
    print(f"Reporte guardado: {out}  ({out.stat().st_size / 1024:.1f} KB)")

    docs = root / "docs" / "index.html"
    if docs.parent.exists():
        import shutil
        shutil.copy2(out, docs)
        print(f"Copiado a:        {docs}")
