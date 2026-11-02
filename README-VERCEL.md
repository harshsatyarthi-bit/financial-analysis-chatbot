# Financial Analysis Chatbot — Vercel deployment

## Files to add to the existing GitHub repository

Copy these files into the repository root:
- `app.py`
- `requirements.txt`
- `.python-version`

Keep the existing dataset file `tech_financials_2023_2025.xlsx` in the repository root, beside `app.py`.
Keep `Financial_Analysis_Chatbot.ipynb` if you want it as a development notebook.

## Why this fixes the current error

The notebook was not a deployable web entry point. `app.py` now exposes a FastAPI ASGI application named `app` at the repository root and mounts the existing Gradio chatbot at `/`. Vercel's current FastAPI integration recognizes root-level `app.py` and detects the `app` instance automatically.

## Deploy

1. Add the three files above to the root of the GitHub repository.
2. Commit and push the changes to the branch connected to Vercel (currently `main`).
3. In Vercel → Project Settings → Build and Development Settings, remove any custom build command or output directory if one was added for a different framework. Leave framework detection/default settings in place.
4. Trigger a new deployment.
5. Open the deployment URL. The Gradio chatbot should load at the root URL.

## Important

The Excel dataset must be committed to the repository root with this exact filename:
`tech_financials_2023_2025.xlsx`

If your workbook has a different filename, either rename it or update `DATA_FILE` in `app.py`.

The application reads the workbook with `header=1`, matching the original notebook. It expects the following columns:
`Company`, `Fiscal Year`, `Total Revenue ($M)`, `Net Income ($M)`, `Total Assets ($M)`, `Total Liabilities ($M)`, `CF from Operations ($M)`.

## Local test (optional)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Then visit `http://127.0.0.1:8000`.

## Note about Vercel

Vercel's Python runtime supports FastAPI applications. This fixes the specific “No python entrypoint found” build error by providing a recognized entry point. Any later runtime error (for example, a dataset column mismatch or package issue) will appear in the new deployment's runtime/build logs and should be debugged separately.
