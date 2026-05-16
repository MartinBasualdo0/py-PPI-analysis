# py-ppi-arg 0.2.1 — Documentación de referencia

Python connector for PortfolioPersonal's REST APIs.  
Autor: Martin Basualdo — [GitHub](https://github.com/MartinBasualdo0/pyPPI)

---

## Instalación

```bash
pip install py_ppi_arg
```

---

## Cambios clave en 0.2.x (respecto a 0.1.x)

- **`otp_provider` callback**: en lugar de `input()` bloqueante, podés pasar una función `Callable[[], str]` que devuelve el código OTP — útil para scripts no interactivos.
- **`_resolve_client_id` con fallback JWT**: si el endpoint `ComitentesAsignados` falla (cuentas restringidas), extrae el `cuentaID` directamente del JWT. Los endpoints de market data siguen funcionando aunque falle.
- **`InstrumentType` enum** formalizado: `CORPORATE = "140"`, `PUBLIC_BOND = "100"`, `LETRAS = "110"`.
- **Session cache (0.2.0 únicamente, removida en 0.2.1)**: existió brevemente en 0.2.0 pero fue revertida. En 0.2.1 cada `PPI()` hace login completo y pide 2FA si no hay `remember_device`.

---

## Inicialización

```python
from py_ppi_arg import PPI

app = PPI(
    user="usuario@email.com",
    password="contraseña",
    remember_device=True,   # intenta que PPI recuerde el dispositivo (reduce 2FA)
    otp_provider=None,      # Callable[[], str] — si se pasa, evita el input() interactivo
)
# Sin cache en disco: cada instancia nueva autentica contra la API.
# Con remember_device=True: PPI puede no pedir 2FA en logins subsiguientes.
```

### Pasar OTP programáticamente (scripts no interactivos)

```python
import pyotp

app = PPI(
    user="...", password="...",
    otp_provider=lambda: pyotp.TOTP("TU_SEED_TOTP").now(),
)
```

---

## Enumeraciones

### `InstrumentType`

| Enum | Valor | Descripción |
|------|-------|-------------|
| `CORPORATE` | `"140"` | Obligaciones Negociables (ONs) |
| `PUBLIC_BOND` | `"100"` | Bonos soberanos, provinciales, corporativos hard-dollar / CER / dólar-link |
| `LETRAS` | `"110"` | Letras del Tesoro (LEDES, LECAP, etc.) |

### `Settlement`

| Enum | Valor | Descripción |
|------|-------|-------------|
| `T0` | `"1"` | Contado inmediato (CI) |
| `T1` | `"2"` | 24hs |
| `T2` | `"3"` | 48hs (igual a T1 en la práctica) |
| `T3` | `"4"` | 72hs |

### `OperationType`

| Enum | Valor | Descripción |
|------|-------|-------------|
| `COMPRA` | `"10000"` | Compra |
| `OTRO` | `"10040"` | Otro |

### `Currency`

| Enum | Valor |
|------|-------|
| `USD` | `"10001"` |

---

## Métodos disponibles

### `get_tickers_list`

Devuelve la lista de cotizaciones de todos los instrumentos de un tipo/settlement.  
**Requiere `clientID`** (lo resuelve automáticamente en `_auth`).  
⚠ Usa el endpoint `/api/Ordenes/InstrumentosOperables` — falla con 401 si la cuenta no tiene permisos de trading. En ese caso, usar `search_tickers` con múltiples prefijos como alternativa.

```python
# Todos los bonos públicos (soberanos + provinciales + corporativos hard-dollar/CER)
bonos = app.get_tickers_list(
    instrument_type=app.instrument_types.PUBLIC_BOND,
    operation_type=app.operation_types.COMPRA,
    settlement=app.settlements.T2,
)

# Todas las letras
letras = app.get_tickers_list(
    instrument_type=app.instrument_types.LETRAS,
    operation_type=app.operation_types.COMPRA,
    settlement=app.settlements.T2,
)

# ONs
ons = app.get_tickers_list(
    instrument_type=app.instrument_types.CORPORATE,
    operation_type=app.operation_types.COMPRA,
    settlement=app.settlements.T2,
)
```

Todos retornan `dict` con clave `"payload"` → lista de instrumentos.

### `search_tickers`

Busca por ticker parcial o por `item_id`.

```python
app.search_tickers(short_ticker="AL30")   # búsqueda por nombre
app.search_tickers(item_id="885981")      # búsqueda por ID
```

### `get_technical_data_bonds`

Datos técnicos de un bono: ISIN, emisor, legislación, flujos teóricos, tasa de renta, etc.

```python
td = app.get_technical_data_bonds(
    settlement=app.settlements.T2,
    item_id="804421",
).get("payload") or {}

flujos = td.get("flujosDeFondosTeoricos") or []
# Cada flujo: {"fechaCorte": "...", "amortizacion": X, "interes": Y, "total": Z, "moneda": "..."}
```

Campos clave del payload:
- `isin`, `emisor`, `legislacion`, `esLeyLocal`
- `tasaRentaAnual`, `ajustaPorCER`, `dolarLink`
- `fechaVencimiento`
- `laminaMinima`
- `flujosDeFondosTeoricos` (lista de flujos futuros)
- `intereses` (estructura de cupones)

### `get_historic_data`

Serie histórica de precios.

```python
hist = app.get_historic_data(
    item_id="261",
    settlement=app.settlements.T2,
    date_from="2024-01-01",   # formato YYYY-MM-DD
    date_to="2024-12-31",
).get("payload") or []

# Cada elemento: {"fechaCotizacion": "...", "ultOperado": X, "cierreAnterior": Y, "volumen": Z}
```

### `get_intraday_data`

Datos intradiarios.

```python
app.get_intraday_data(item_id="261", settlement=app.settlements.T2)
```

---

## Ejemplo completo: fetch de bonos y letras

```python
from py_ppi_arg import PPI
import os

app = PPI(user=os.environ["PPI_USER"], password=os.environ["PPI_PASSWORD"])

# Bonos públicos (soberanos + provinciales + corporativos)
bonos_payload = app.get_tickers_list(
    instrument_type=app.instrument_types.PUBLIC_BOND,
    operation_type=app.operation_types.COMPRA,
    settlement=app.settlements.T2,
).get("payload") or []

# Letras
letras_payload = app.get_tickers_list(
    instrument_type=app.instrument_types.LETRAS,
    operation_type=app.operation_types.COMPRA,
    settlement=app.settlements.T2,
).get("payload") or []

# Campos típicos de cada item en el payload:
# item["id"]            → ID numérico del instrumento
# item["ticker"]        → ej. "AL30", "TX26", "LEDES"
# item["descripcion"]   → nombre completo
# item["moneda"]        → {"id": ..., "descripcion": "Dólar MEP / CCL / Peso / ..."}
# item["tipoItem"]      → {"id": "100"/"110"/"140", "descripcion": "..."}
# item["operable24"]    → bool
# item["ultimoPrecio"]  → precio en cotización actual (si disponible)
```

---

## Notas de uso

- Los flujos en `flujosDeFondosTeoricos` están expresados **por cada 100 de VN** (valor nominal).
- Para CER/UVA: los flujos ya incluyen el ajuste vigente al día de consulta; no proyectan inflación futura.
- Para dólar-link: flujos en ARS ajustados por el tipo de cambio oficial vigente.
- `get_tickers_list` puede requerir `clientID` válido; `search_tickers` y `get_technical_data_bonds` no lo requieren.
