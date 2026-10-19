# U1 ataskaita

## Kas padaryta

- **R1:** repo struktūra (`src/`, `docker/`, `k8s/`, `docs/`), README su paleidimu nuo nulio, `docs/requirements.md`
  v1.4: 5 FR ir 14 NFR su KPI ir išmatuotomis reikšmėmis.
- **R2:** DVC pipeline'as `prepare → train → evaluate`, `params.yaml`, commit'intas `dvc.lock`, lokalus DVC remote;
  3 run'ai klasterio MLflow (`max_depth` 5 / 10 / 15) su požymių svarba ir klaidų matrica; `reproduce.py` atkūrė
  run'ą per 20 s, Δ = 0.
- **R3:** viešas vaizdas `ghcr.io/lukasja111/mlops-u1/train:sha-71249941`: rootfs 449,63 MB, Trivy CRITICAL 0 /
  HIGH 44, uid 1000, SBOM.
- **R4:** kind klasteris, namespace `mlops-u1`, PostgreSQL ir MLflow su PVC per `127.0.0.1:5000`; run'ai išliko
  perkūrus Pod'us; DB slaptažodis ne procesų argumentuose.
- **E2:** mokymas kaip Kubernetes Job su GHCR vaizdu, hiperparametrai per ConfigMap; metrikos sutampa su `dvc repro`.

## Kas neveikė / ką teko spręsti

1. **Duomenų nutekėjimas:** tas pats skelbimas yra ir darbo dienų, ir savaitgalio faile, todėl atsitiktinis
   padalijimas 64,5 % testinių eilučių paliko dvynį mokymo imtyje, ir gylio 15 F1 0,7197 buvo išpūstas. Dabar
   skaidoma pagal vietą (`StratifiedGroupKFold`, NFR-01a): F1 0,6298, KPI tenkina tik gylis 15; seni run'ai
   pažymėti `split=random`.
2. **Žemas F1:** Superhost tik 25,6 %, todėl gylis 5 be klasių svorių davė F1 0,227; `class_weight="balanced"`
   pakėlė jį iki 0,595–0,630.
3. **Kurso `train.py` su RandomForest lūžta** (skops `UntrustedTypesFoundException`): pridėta
   `skops_trusted_types=["sklearn.tree._tree.Tree"]`.
4. **MLflow serveris netilpo į 2 GiB** (kurso komanda: 18 procesų, 2,2 GB): `requests` 2560Mi, `limits` 3Gi.
5. **HIGH CVE `cryptography` 49.0.0** su pilnu `mlflow`: vaizde `mlflow-skinny`, 745 → 450 MB, Python radinių nebeliko.
6. **NixOS aplinka:** nixpkgs `dvc` sugadino venv, wheel'ams trūko `libstdc++`, `gh` nebuvo PATH; sprendimas: `dvc`
   venv'e, `LD_LIBRARY_PATH` ir `gh` lokaliame `shell.nix`.
7. **Nedaryta:** E1, E3, E4, E5.

## Kiek laiko užtruko

~7 val.
