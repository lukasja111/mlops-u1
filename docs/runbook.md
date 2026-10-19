# Naudojimo instrukcijos

Papildymas prie README: repo struktūra, duomenys be DVC remote, naujas eksperimentas, reprodukcija, Docker vaizdas,
Job'o detalės ir problemų sprendimas. Komandos vykdomos repo šaknyje su aktyvuotu `.venv` ir
`MLFLOW_TRACKING_URI=http://127.0.0.1:5000`.

## Repo struktūra

```
src/                   data_prep.py, train.py, eval.py
reproduce.py           istorinio run'o atkūrimas pagal run_id
dvc.yaml, params.yaml  pipeline'as ir hiperparametrai; dvc.lock, metrics.json commit'inami
data/raw.dvc           20 CSV rodyklė (patys duomenys DVC remote, ne Git)
models/run_id.txt      paskutinio mokymo MLflow run_id
docker/Dockerfile.train, .dockerignore, requirements-train.txt   mokymo vaizdas
k8s/kind-config.yaml   klasterio konfigūracija; k8s/namespace.yaml
k8s/mlflow/            Postgres ir MLflow: PVC, Deployment, Service
k8s/jobs/              E2: ConfigMap (MLflow adresas, hiperparametrai) ir mokymo Job
scripts/publish.sh     vaizdo publikavimas į GHCR
docs/                  requirements.md, architecture.md, runbook.md, image-sizes.md, security-scan.md,
                       u1-report.md, trivy-train.json, sbom-train.json
```

`requirements-train.txt`: mokymo priklausomybės (jas diegia ir Docker vaizdas, su `mlflow-skinny`);
`requirements.txt`: plius pilnas `mlflow`; `requirements-dev.txt`: plius DVC. Tiesioginės priklausomybės fiksuotos `==`.

## Duomenys be DVC remote

`localremote` yra autoriaus kompiuterio katalogas, todėl kitur `dvc pull` baigiasi klaida, o README 4 žingsnis tuos
pačius 20 CSV atsisiunčia iš fiksuotos HF revizijos. `dvc commit` suskaičiuoja katalogo md5 ir įdeda failus į DVC
cache (jo reikia `reproduce.py`). Jei `git diff` rodo pakeitimą, failai skiriasi nuo autoriaus (md5
`a2b156db54022d6fe3c950258a5d5c9a.dir`). `dvc push` veiks tik su savu remote:
`dvc remote modify --local localremote url /jusu/katalogas`.

## Naujas eksperimentas

```bash
# params.yaml: pakeiskite hiperparametrą, pvz. train.max_depth 15 -> 10
dvc status                             # train: changed deps, params.yaml: modified
dvc repro                              # persileidžia tik train ir evaluate (prepare nuo params nepriklauso)
dvc params diff && dvc metrics diff
git commit -am "exp: max_depth 10"
dvc push                               # tik su savu remote, žr. „Duomenys be DVC remote“
```

- `dvc.lock` pasikeičia: `train` params reikšmė ir `models/model.pkl`, `models/run_id.txt`, `metrics.json` md5;
  `prepare` įrašas lieka toks pat.
- Antras `dvc repro` be pakeitimų nieko neperskaičiuoja (`didn't change, skipping`).
- **Kodo pakeitimus (`src/`) commit'inkite prieš `dvc repro`:** run'o `git_commit` tag'as yra HEAD mokymo metu, o
  `reproduce.py` atkuria būtent tą commit'ą. Keičiant tik `params.yaml` iš anksto commit'inti nereikia: `reproduce.py`
  hiperparametrus ima iš run'o.

## Reprodukcija

```bash
git status                             # švarus darbo medis, esate šakoje (main)
time python reproduce.py <run_id>      # ≤ 2 min, |Δaccuracy| ≤ 0,005, |Δf1| ≤ 0,005
```

`<run_id>`: README 5 žingsnio išvestyje (`run_id=…`) arba MLflow UI; `models/run_id.txt` rodo tik paskutinį run'ą.
Naujame klasteryje atkurkite savo run'ą: autoriaus run'ų jame nėra.

`reproduce.py`: paima run'ą iš MLflow → `git checkout <git_commit>` → `dvc checkout` žalių duomenų → run'o
hiperparametrai į `params.yaml` → `dvc repro --force` → palygina metrikas, naujam run'ui uždeda tag'ą
`reproduces=<run_id>` → grąžina repo į pradinę šaką. Pavyzdys (`rf-n100-d5`):

```
accuracy: original=0.7121 reproduced=0.7121 delta=0.0000
f1: original=0.5947 reproduced=0.5947 delta=0.0000
REPRODUCED in 20s -> new run 4fbc102c1ee841c181489d5ba145deca
```

## Docker vaizdas

Reikia [Trivy](https://trivy.dev/) ir [gh](https://cli.github.com/) (`gh auth login --scopes write:packages`);
išbandyta su Trivy 0.72.0, gh 2.102.0.

```bash
SHA=$(git rev-parse --short=8 HEAD)
docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=$SHA -t mlops-u1/train:sha-$SHA .
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 mlops-u1/train:sha-$SHA

trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output docs/trivy-train.json mlops-u1/train:sha-$SHA
trivy image --scanners vuln --severity CRITICAL --exit-code 1 mlops-u1/train:sha-$SHA
trivy image -f spdx-json -o docs/sbom-train.json mlops-u1/train:sha-$SHA
bash scripts/publish.sh
```

- Vaizdas kopijuoja `data/processed/`, todėl prieš `docker build` reikia `dvc pull` arba `dvc repro`.
- Tag'as `sha-<8 simboliai>` sutampa su MLflow `git_commit` tag'u ir vaizdo `org.opencontainers.image.revision`
  žyme; `latest` nenaudojamas. Kitas commit'as duoda kitą tag'ą, todėl Trivy komandos kartojamos.
- Trivy komandos perrašo commit'intus `docs/trivy-train.json` ir `docs/sbom-train.json`: naujus commit'inkite arba
  atkurkite `git checkout -- docs/` (prieš `reproduce.py`, nes jis daro `git checkout --force`).
- `--network host` veikia Linux'e; kitur `-e MLFLOW_TRACKING_URI=http://host.docker.internal:5000`.
- `scripts/publish.sh` (reikia `gh` ir `trivy`): CRITICAL vartas, prisijungimas prie GHCR su `gh` token'u, push ir
  digest. Naujas GHCR paketas būna privatus: viešu jį padaro GitHub → Packages → Package settings.
- Publikuotas vaizdas, jo dydis ir Trivy rezultatai: `docs/image-sizes.md`, `docs/security-scan.md`.

## E2: Job'o detalės

- Job'as paleidžia viešą GHCR vaizdą `sha-71249941`, todėl nieko kurti ar įkelti į kind nereikia. Tag'as yra
  commit'as, iš kurio vaizdas sukurtas, o ne dabartinis HEAD: manifestas negali nurodyti commit'o, kuriame pats
  įrašytas. Naujam vaizdui: sukurti ir publikuoti (žr. „Docker vaizdas“), tada pakeisti `image:`
  `k8s/jobs/job-train.yaml`.
- MLflow pasiekiamas per `http://mlflow:5000` (ConfigMap); todėl MLflow paleistas su `--allowed-hosts`, kitaip
  atsakytų `403 Invalid Host header`.
- Hiperparametrai `N_ESTIMATORS` ir `MAX_DEPTH` yra ConfigMap `training-config`; Job'as juos perduoda `train.py`
  argumentais. ConfigMap skaitomas paleidžiant Pod'ą, todėl pakeitimas galioja kitam Job'ui:

  ```bash
  sed -i 's/MAX_DEPTH: "15"/MAX_DEPTH: "10"/' k8s/jobs/configmap-training.yaml
  kubectl apply -f k8s/jobs/configmap-training.yaml
  kubectl -n mlops-u1 delete job train && kubectl apply -f k8s/jobs/job-train.yaml
  kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
  ```

- Job'ai nekeičiami: pakartotinai paleisti `kubectl -n mlops-u1 delete job train` ir vėl tas pats `apply`.
- Išbandyta: run'as `bb5f031f` su `git_commit=71249941` davė tas pačias metrikas kaip `dvc repro` (0,7764 / 0,6298),
  o su `MAX_DEPTH: "10"` run'as `64eda7cc` davė tas pačias kaip gylio 10 run'as (0,7440 / 0,6181). Vaizdas
  atsisiųstas per 2,2 s; Job'as su jau atsisiųstu vaizdu baigėsi per 20 s.

## Problemų sprendimas

| Simptomas | Priežastis ir sprendimas |
|---|---|
| `MLFLOW_TRACKING_URI wasn't set properly` | Kintamasis nenustatytas šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| `403 Invalid Host header` | Host'o nėra MLflow `--allowed-hosts` sąraše (`k8s/mlflow/deployment-mlflow.yaml`) |
| `curl 127.0.0.1:5000` atmeta ryšį | Klasteris sukurtas be `k8s/kind-config.yaml` (portai nustatomi tik kuriant: ištrinkite ir sukurkite iš naujo) arba MLflow Pod'as dar neparengtas (`kubectl -n mlops-u1 get pods`) |
| macOS: 5000 portas užimtas | Jį naudoja AirPlay Receiver: išjunkite jį arba `k8s/kind-config.yaml` pakeiskite `hostPort` (pvz. 5001) ir atitinkamai `MLFLOW_TRACKING_URI` |
| Postgres Pod'as `CrashLoopBackOff` | Secret sukurtas su tuščiu slaptažodžiu (`PG_PASSWORD` nenustatytas): `kubectl -n mlops-u1 delete secret postgres-credentials`, sukurkite jį iš naujo ir ištrinkite abu Pod'us (`-l app=postgres`, `-l app=mlflow`) |
| `dvc repro` nieko nedaro naujame klasteryje | Po `dvc pull` išvestys sutampa su `dvc.lock`: `dvc repro --force` |
