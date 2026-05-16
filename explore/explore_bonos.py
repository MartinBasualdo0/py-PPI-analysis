"""
Script de exploración para descubrir la estructura de bonos y letras en la API de PPI.

Usa get_tickers_list con PUBLIC_BOND (100) y LETRAS (110) para obtener el universo completo,
luego inspecciona los campos de moneda/tipo para entender cómo clasificar CER, dólar-link, etc.

Salida:
  output/_bonos_items.json      — todos los ítems de PUBLIC_BOND + LETRAS
  output/_bonos_sample_td.json  — datos técnicos de AL30 (flujos, campos disponibles)

Uso:
    python explore/explore_bonos.py
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from py_ppi_arg import PPI

load_dotenv(Path(__file__).parent.parent / ".env")

ROOT    = Path(__file__).parent.parent
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    app = PPI(
        user=os.environ["PPI_USER"],
        password=os.environ["PPI_PASSWORD"],
        remember_device=True,
    )
    print("Auth OK.\n")

    # ── 1. Obtener universo completo via search_tickers ───────────────────────
    # get_tickers_list requiere permisos de Ordenes — usamos search_tickers
    # con prefijos que cubren el universo de bonos y letras argentinos.
    SEARCH_TERMS = [
        # Soberanos hard dollar
        "AL", "GD", "AE", "AA",
        # CER / UVA
        "TX", "PR", "DICP", "CUAP",
        # Dólar-link
        "TV", "TDA", "T2V", "T3V",
        # Letras (LECAP, LEDES)
        "LEDE", "LECAP", "S1", "S2", "S3", "S4", "S5", "S6",
        # Provinciales
        "BPY", "PBA", "CO2", "NQ", "SF", "ME", "LP", "EN",
        # Corporativos / cuasi-soberanos
        "YPF", "NDT", "YPFD",
    ]

    seen_ids: set = set()
    all_items: list[dict] = []

    for term in SEARCH_TERMS:
        try:
            payload = app.search_tickers(short_ticker=term).get("payload") or []
            for item in payload:
                ti_id = (item.get("tipoItem") or {}).get("id")
                item_id = item.get("id")
                # Solo bonos (100) y letras (110), sin duplicados
                if ti_id in {100, "100", 110, "110"} and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    all_items.append(item)
        except Exception as e:
            print(f"  ERROR buscando '{term}': {e}")

    print(f"Total ítems únicos (tipoItem 100+110): {len(all_items)}")

    # ── 2. Parsear campos clave ───────────────────────────────────────────────
    rows = []
    for item in all_items:
        ti    = item.get("tipoItem") or {}
        mon   = item.get("moneda")   or {}
        rows.append({
            "id":              item.get("id"),
            "ticker":          item.get("ticker"),
            "descripcion":     item.get("descripcion"),
            "tipoItem_id":     ti.get("id"),
            "tipoItem_desc":   ti.get("descripcion"),
            "moneda_id":       mon.get("id"),
            "moneda_desc":     mon.get("descripcion"),
            "operable24":      item.get("operable24"),
            "ultimoPrecio":    item.get("ultimoPrecio"),
            # Campos que podrían indicar CER / dólar-link / tipo
            "ajustaPorCER":    item.get("ajustaPorCER"),
            "dolarLink":       item.get("dolarLink"),
            "tipoRenta":       item.get("tipoRenta"),
            "subTipo":         item.get("subTipo"),
        })

    df = pd.DataFrame(rows)

    # ── 3. Resumen de monedas (clave para clasificar categorías) ──────────────
    print("\n=== Distribución por moneda ===")
    print(df.groupby(["moneda_id", "moneda_desc"]).size().reset_index(name="count").to_string(index=False))

    print("\n=== Distribución por tipoItem ===")
    print(df.groupby(["tipoItem_id", "tipoItem_desc"]).size().reset_index(name="count").to_string(index=False))

    # ── 4. Mostrar todos los campos disponibles en el primer ítem ─────────────
    if all_items:
        print("\n=== Campos disponibles en un ítem ===")
        sample_keys = list(all_items[0].keys())
        print(sample_keys)
        print("\nValores del primer ítem:")
        print(json.dumps(all_items[0], indent=2, ensure_ascii=False, default=str))

    # ── 5. Muestra de tickers por moneda ─────────────────────────────────────
    print("\n=== Muestra de tickers por moneda ===")
    for (mon_id, mon_desc), grp in df.groupby(["moneda_id", "moneda_desc"]):
        sample = ", ".join(grp["ticker"].dropna().head(8).tolist())
        print(f"  [{mon_id}] {mon_desc:<30} ({len(grp):>3} ítems)  →  {sample}")

    # ── 6. Campos extra que podrían indicar tipo de bono ─────────────────────
    extra_cols = ["ajustaPorCER", "dolarLink", "tipoRenta", "subTipo"]
    for col in extra_cols:
        if df[col].notna().any():
            print(f"\n=== Valores únicos de '{col}' ===")
            print(df[col].value_counts(dropna=False).to_string())

    # ── 7. Guardar JSON completo ──────────────────────────────────────────────
    out_items = OUT_DIR / "_bonos_items.json"
    out_items.write_text(json.dumps(all_items, indent=2, ensure_ascii=False, default=str))
    print(f"\nGuardado: {out_items}  ({len(all_items)} ítems)")

    # ── 8. Datos técnicos de AL30 ─────────────────────────────────────────────
    al30 = df[df["ticker"] == "AL30"]
    if al30.empty:
        al30 = df[df["ticker"].str.startswith("AL30", na=False)]
    if not al30.empty:
        item_id = str(int(al30.iloc[0]["id"]))
        print(f"\n=== Datos técnicos AL30 (id={item_id}) ===")
        try:
            td = app.get_technical_data_bonds(
                settlement=app.settlements.T2, item_id=item_id
            ).get("payload") or {}
            sample = {k: v for k, v in td.items() if k != "flujosDeFondosTeoricos"}
            print(json.dumps(sample, indent=2, ensure_ascii=False, default=str))
            flujos = td.get("flujosDeFondosTeoricos") or []
            if flujos:
                print(f"\nFlujos ({len(flujos)} total) — primeros 2:")
                print(json.dumps(flujos[:2], indent=2, ensure_ascii=False, default=str))
            out_td = OUT_DIR / "_bonos_sample_td.json"
            out_td.write_text(json.dumps(td, indent=2, ensure_ascii=False, default=str))
            print(f"Guardado: {out_td}")
        except Exception as e:
            print(f"ERROR obteniendo TD de AL30: {e}")
    else:
        print("\nAL30 no encontrado en el universo.")


if __name__ == "__main__":
    main()
