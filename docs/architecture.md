# Architektūra

DVC pipeline'as veikia kūrėjo kompiuteryje, o MLflow serveris (su PostgreSQL ir artefaktų PVC): lokaliame
kind klasteryje. Žali duomenys (20 CSV iš fiksuotos HF revizijos) versijuojami DVC. Kiekvienas mokymas sukuria
MLflow run'ą klasteryje; `dvc.lock` ir run'o `git_commit` / `dvc_raw_md5` tag'ai juos susieja.

```mermaid
flowchart LR
    hf["Hugging Face<br/>kraina/airbnb · rev b9dd71fc"]
    remote[("DVC remote<br/>~/dvcstore")]
    subgraph pc["Kūrėjo kompiuteris"]
        raw["data/raw/ · 20 CSV"] --> prep["data_prep.py"] --> train["train.py"] --> ev["eval.py"]
    end
    subgraph k8s["kind klasteris mlops-u1 · namespace mlops-u1"]
        mlflow["MLflow · NodePort 30500"] --> pg[("PostgreSQL · PVC")]
        mlflow --> art[("Artefaktų PVC")]
        job["E2: mokymo Job"]
    end
    hf -->|curl| raw
    raw <-->|"dvc push / pull"| remote
    train -->|"127.0.0.1:5000"| mlflow
    ev -->|"eval/* metrikos"| mlflow
    img["Docker vaizdas · ghcr.io/…/train:sha-8"] -.-> job
    job -->|"http://mlflow:5000"| mlflow
```
