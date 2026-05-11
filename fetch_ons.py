"""
Fetching completo de Obligaciones Negociables desde la API de PPI.

Salida: output/on_tir.parquet  (consumido por on_report.py)

Uso:
    python fetch_ons.py              # todas las ONs
    python fetch_ons.py --limit 10   # solo 10, para testear rápido
    python fetch_ons.py --resume     # retomar si se interrumpió
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from py_ppi_arg import PPI

load_dotenv(Path(__file__).parent / ".env")

ROOT        = Path(__file__).parent
OUT_DIR     = ROOT / "output"
CHECKPOINT  = OUT_DIR / "_fetch_checkpoint.jsonl"   # una línea JSON por bond
SAMPLE_FILE = OUT_DIR / "_td_sample.json"            # campos técnicos de muestra


# ── helpers de TIR ────────────────────────────────────────────────────────────

def _npv(rate: float, flows: list[dict], today_dt: datetime) -> float:
    s = 0.0
    for f in flows:
        fd = pd.to_datetime(f["fechaCorte"]).to_pydatetime()
        if fd.tzinfo is not None:
            fd = fd.astimezone(timezone.utc).replace(tzinfo=None)
        days = (fd - today_dt).days
        if days <= 0:
            continue
        s += f["total"] / (1 + rate) ** (days / 365.0)
    return s


def _ytm(flows: list[dict], price: float, today_dt: datetime) -> float | None:
    lo, hi, tol = -0.5, 5.0, 1e-6
    f_lo = _npv(lo, flows, today_dt) - price
    f_hi = _npv(hi, flows, today_dt) - price
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, flows, today_dt) - price
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return (lo + hi) / 2


# ── helpers de mercado ────────────────────────────────────────────────────────

def _quote_market(item: dict) -> str:
    m = item.get("moneda") or {}
    desc = (m.get("descripcion") or "").lower()
    if "mep" in desc:
        return "USD MEP"
    if "ccl" in desc or m.get("id") == 10001:
        return "USD CCL"
    if "peso" in desc or m.get("id") == 10000:
        return "ARS"
    return "OTRO"


def _min_denomination(td: dict) -> float | None:
    val = td.get("laminaMinima")
    if val is not None:
        try:
            v = float(val)
            return v if v > 0 else None
        except (TypeError, ValueError):
            pass
    return None


# ── checkpoint ────────────────────────────────────────────────────────────────

def _load_checkpoint() -> tuple[set[int], list[dict]]:
    """Lee el checkpoint y devuelve (ids ya procesados, filas ya fetcheadas)."""
    if not CHECKPOINT.exists():
        return set(), []
    done_ids, rows = set(), []
    for line in CHECKPOINT.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            done_ids.add(row["id"])
            rows.append(row)
    return done_ids, rows


def _append_checkpoint(row: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")


# ── fetching principal ────────────────────────────────────────────────────────

def fetch(limit: int | None = None, resume: bool = False) -> pd.DataFrame:
    app = PPI(
        user=os.environ["PPI_USER"],
        password=os.environ["PPI_PASSWORD"],
        remember_device=True,
    )
    print(f"Auth OK. Token expira: {app._token_expires_at}")

    all_items = app.search_tickers(short_ticker="ON").get("payload") or []
    ons = [
        i for i in all_items
        if isinstance(i.get("tipoItem"), dict)
        and i["tipoItem"].get("id") == 140
        and i.get("operable24")
    ]
    print(f"ONs operables 24h: {len(ons)}")
    print("Por mercado:", dict(Counter(_quote_market(i) for i in ons)))

    # Checkpoint: si --resume, saltear los ids ya procesados
    done_ids, checkpoint_rows = set(), []
    if resume and CHECKPOINT.exists():
        done_ids, checkpoint_rows = _load_checkpoint()
        print(f"Retomando: {len(done_ids)} bonds ya procesados en checkpoint")

    today     = date.today()
    date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    date_to   = today.strftime("%Y-%m-%d")
    iterable  = ons[:limit] if limit else ons

    rows   = list(checkpoint_rows)
    errors = 0
    sample_saved = SAMPLE_FILE.exists()   # no sobreescribir si ya existe una buena

    t0 = time.time()
    skipped = 0

    for n, item in enumerate(iterable, 1):
        sid = item["id"]

        if sid in done_ids:
            skipped += 1
            continue

        ticker      = item.get("ticker")
        descripcion = item.get("descripcion")

        try:
            td_resp = app.get_technical_data_bonds(
                settlement=app.settlements.T2, item_id=str(sid)
            )
            td = td_resp.get("payload") or {}

            flujos = td.get("flujosDeFondosTeoricos") or []
            if not flujos:
                continue

            # Guardar muestra de campos técnicos del primer bond con datos reales
            if not sample_saved:
                sample = {k: v for k, v in td.items() if k != "flujosDeFondosTeoricos"}
                SAMPLE_FILE.write_text(json.dumps(sample, indent=2, ensure_ascii=False, default=str))
                print(f"\n── Campos técnicos ({ticker}) ──")
                print(json.dumps(sample, indent=2, ensure_ascii=False, default=str))
                print("────────────────────────────────\n")
                sample_saved = True

            hist = app.get_historic_data(
                item_id=str(sid),
                settlement=app.settlements.T2,
                date_from=date_from,
                date_to=date_to,
            ).get("payload") or []
            if not hist:
                continue

            last  = hist[-1]
            price = last.get("ultOperado") or last.get("cierreAnterior")
            if not price or price <= 0:
                continue

            # Volumen del último día completo con operaciones (no del día en curso)
            last_with_vol = next((h for h in reversed(hist) if (h.get("volumen") or 0) > 0), None)
            volumen = last_with_vol["volumen"] if last_with_vol else 0

            price_dt      = pd.to_datetime(last["fechaCotizacion"]).normalize().to_pydatetime().replace(tzinfo=None)
            settlement_dt = (pd.Timestamp(price_dt) + pd.offsets.BDay(1)).to_pydatetime()

            tir = _ytm(flujos, price, settlement_dt)
            if tir is None:
                continue

            row = {
                "id":               sid,
                "ticker":           ticker,
                "descripcion":      descripcion,
                "isin":             td.get("isin"),
                "emisor":           td.get("emisor"),
                "legislacion":      td.get("legislacion"),
                "es_ley_local":     td.get("esLeyLocal"),
                "tasa_renta_anual": td.get("tasaRentaAnual"),
                "ajusta_cer":       td.get("ajustaPorCER", False),
                "dolar_link":       td.get("dolarLink", False),
                "fechaVencimiento": td.get("fechaVencimiento"),
                "price":            price,
                "price_date":       last.get("fechaCotizacion"),
                "volumen":          volumen,
                "moneda_cotizacion": _quote_market(item),
                "moneda_emision":   "USD" if "U$S" in (descripcion or "") else (flujos[0].get("moneda") or "?").upper(),
                "lamina_minima":    _min_denomination(td),
                "flujos":           flujos,
                "intereses":        td.get("intereses"),
                "tir":              tir,
                "tir_pct":          tir * 100,
            }
            rows.append(row)
            _append_checkpoint(row)

        except KeyboardInterrupt:
            print(f"\n\nInterrumpido en {n}/{len(iterable)}. Checkpoint guardado ({len(rows)} bonds).")
            print(f"Retomá con: python fetch_ons.py --resume")
            sys.exit(0)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR {ticker}: {e}")

        if n % 50 == 0:
            elapsed = time.time() - t0
            rate    = (n - skipped) / elapsed if elapsed > 0 else 0
            remaining = (len(iterable) - n) / rate if rate > 0 else 0
            print(
                f"  {n:>4}/{len(iterable)}  guardados: {len(rows):>3}  "
                f"errores: {errors}  ~{remaining/60:.0f} min restantes"
            )

    print(f"\nFinal: {len(rows)} ONs con TIR (de {len(iterable) - skipped} procesadas, {errors} errores)")
    df = _build_df(rows)

    # Limpiar checkpoint si terminó OK
    if CHECKPOINT.exists() and not limit:
        CHECKPOINT.unlink()
        print("Checkpoint eliminado.")

    return df


def _build_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["fechaVencimiento"] = pd.to_datetime(df["fechaVencimiento"], errors="coerce", utc=True).dt.tz_convert(None)
    df["price_date"]       = pd.to_datetime(df["price_date"],       errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=["fechaVencimiento", "tir_pct"])
    df = df[df["fechaVencimiento"] >= pd.Timestamp.now().normalize()]
    df = df.sort_values("fechaVencimiento").reset_index(drop=True)

    print(f"\nMoneda cotización: {df['moneda_cotizacion'].value_counts().to_dict()}")
    print(f"Moneda emisión:    {df['moneda_emision'].value_counts().to_dict()}")

    n_lam = df["lamina_minima"].notna().sum()
    print(f"Lámina mínima:     {n_lam}/{len(df)} bonds con dato")
    if n_lam:
        sample = (
            df[df["lamina_minima"].notna()]
            [["ticker", "lamina_minima", "es_ley_local", "legislacion"]]
            .drop_duplicates("lamina_minima")
            .head(8)
        )
        print(sample.to_string(index=False))

    return df


def save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df_save = df.copy()
    df_save["flujos"]    = df_save["flujos"].apply(json.dumps)
    df_save["intereses"] = df_save["intereses"].apply(json.dumps)
    df_save.to_parquet(path, index=False)
    print(f"\nGuardado: {path.resolve()}  ({len(df_save)} filas, {path.stat().st_size/1024:.0f} KB)")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int,  default=None,  help="Limitar a N bonds")
    parser.add_argument("--resume", action="store_true",       help="Retomar desde checkpoint")
    parser.add_argument("--out",    type=str,  default=None,   help="Ruta de salida del parquet")
    args = parser.parse_args()

    df  = fetch(limit=args.limit, resume=args.resume)
    out = Path(args.out) if args.out else OUT_DIR / "on_tir.parquet"
    save(df, out)
