# Docker vaizdo dydis

MB = 1 000 000 baitų. **Rootfs**: išpakuotų failų dydis (`du -sx --apparent-size --block-size=1 /`, tas pats metodas
kaip kurso `scripts/week3.py sizes`). Docker `.Size` priklauso nuo image store (čia `overlay2`, nesuspaustas turinys),
todėl su rootfs jo nepainioti.

| Vaizdas | Image ID | Platforma | Bazė | Docker .Size MB | Rootfs MB |
|---|---|---|---|---:|---:|
| `mlops-u1/train:sha-0a26641f` | `sha256:4fbf02538b4f` | linux/amd64 | `python:3.12.14-slim-trixie` | 464,85 | 449,63 |

Vaizdas sukurtas iš commit'o `0a26641f` (jame `docker/Dockerfile.train`). Kitas commit'as duoda naują tag'ą ir
image ID, tada dydis ir Trivy matuojami iš naujo.

## GHCR

| | |
|---|---|
| Vaizdas | `ghcr.io/lukasja111/mlops-u1/train:sha-0a26641f` |
| Digest | `sha256:74fbf9921a9e6c76ab8c86170d1991c24db62ca24e44ced6fef351ed9b81ea8a` |
| Prieiga | vieša; `docker pull` veikia be prisijungimo (patikrinta su tuščia Docker konfigūracija) |
| Paketas | <https://github.com/users/lukasja111/packages/container/package/mlops-u1%2Ftrain>, su repo susietas per `org.opencontainers.image.source` |
| `org.opencontainers.image.revision` | `0a26641f`: tas pats kaip tag'as ir MLflow `git_commit` |

```bash
docker pull ghcr.io/lukasja111/mlops-u1/train@sha256:74fbf9921a9e6c76ab8c86170d1991c24db62ca24e44ced6fef351ed9b81ea8a
```

Tag'as `sha-0a26641f` nurodo commit'ą, digest'as tiksliai fiksuoja paskelbtą turinį; `latest` nenaudojamas.

## Kur dingsta vieta

- Bazė `python:3.12.14-slim-trixie`: 115,88 MB.
- `/opt/venv`: 323,47 MB. Didžiausi paketai: `scipy` 80,49 MB (+ `scipy.libs` 31,20 MB), `pandas` 43,13 MB,
  `sklearn` 30,68 MB, `numpy` 28,74 MB (+ `numpy.libs` 27,46 MB), `cryptography` 14,92 MB, `mlflow` (skinny) 14,39 MB.
- Mokymo duomenys `data/processed/`: 10,49 MB. Jie įdėti į vaizdą, nes Job'as klasteryje nepasiekia lokalaus DVC remote.

## Kodėl `mlflow-skinny`

Mokymui reikia tik MLflow kliento, todėl vaizdas diegia `requirements-train.txt` su `mlflow-skinny==3.15.2`. Pilnas
`mlflow` paketas pridėtų serverio priklausomybes: 34 paketus, tarp jų `pyarrow`, Flask, SQLAlchemy, alembic, gunicorn ir
matplotlib. Palyginimas su tuo pačiu Dockerfile ir duomenimis (2026-10-19):

| Variantas | Rootfs MB | Trivy HIGH |
|---|---:|---:|
| `mlflow-skinny` (publikuotas) | 449,63 | 44 |
| pilnas `mlflow` | 745,10 | 46 |

Run'as iš vaizdo (`ab5eb281`) davė tas pačias metrikas kaip `dvc repro` (`33f81f33`): accuracy 0,8279, F1 0,7197.

## NFR-11 tikslas

Rootfs ≤ 500 MB (kurso 3 savaitės CPU vaizdo tikslas). Išmatuota: 449,63 MB.
