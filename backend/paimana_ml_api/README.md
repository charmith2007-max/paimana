# PAIMANA ML Risk API v1.2

This version retrains the Random Forest under **scikit-learn 1.9.0** so the serialized model matches the runtime and avoids InconsistentVersionWarning.

## Windows setup

```powershell
pip install -r requirements.txt
python train_model.py
uvicorn app:app --reload
```

Open http://127.0.0.1:8000/docs

## Prediction

`POST /predict`

```json
{"project_id":"220100184"}
```

The API finds the latest available ML feature row for that project and generates a fresh prediction.
