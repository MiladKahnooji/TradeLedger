# TradeLedger

A small, open-source local trading journal for Forex and Gold. TradeLedger uses Streamlit, SQLite, and Plotly and stores everything on your own computer.

## Requirements

Python 3.12 and a recent Windows or Linux terminal.

## Install and run

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` first.

### Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app creates `tradeledger.db` on first run. It is intentionally ignored by Git; do not put real trading data in the repository.

## Tests and checks

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The optional **Demo data** action in the sidebar adds sample records only when you explicitly click it.

## License

MIT. See [LICENSE](LICENSE).
