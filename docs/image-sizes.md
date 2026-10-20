# Docker vaizdo dydis

MB = 1 000 000 baitų. **Rootfs**: išpakuotų failų dydis (`du -sx --apparent-size --block-size=1 /`, tas pats metodas
kaip kurso `scripts/week3.py sizes`). Docker `.Size` priklauso nuo image store (čia `overlay2`, nesuspaustas turinys),
todėl su rootfs jo nepainioti.

| Vaizdas | Image ID | Platforma | Bazė | Docker .Size MB | Rootfs MB |
|---|---|---|---|---:|---:|
| `mlops-u1/train:sha-08fbb275` | `sha256:90451178305a` | linux/amd64 | `python:3.12.14-slim-trixie` | 464,89 | 449,68 |

- **NFR-11:** rootfs ≤ 500 MB (kurso 3 savaitės CPU vaizdo tikslas); išmatuota 449,68 MB.
- **Kur dingsta vieta:** bazė 115,67 MB, `/opt/venv` 323,51 MB (didžiausi `scipy`, `pandas`, `sklearn`, `numpy`),
  mokymo duomenys `data/processed/` 10,49 MB: jie įdėti į vaizdą, nes Job'as klasteryje nepasiekia lokalaus DVC remote.
- **Kodėl `mlflow-skinny`:** mokymui reikia tik MLflow kliento. Pilnas `mlflow` su tuo pačiu Dockerfile duotų
  745,10 MB ir 46 HIGH (vietoje 449,68 MB ir 44).
- Vaizdas sukurtas iš commit'o `08fbb275`; kitas commit'as duoda naują tag'ą ir image ID, tada dydis ir Trivy
  matuojami iš naujo. Run'as iš vaizdo (`0a566f99`) davė tas pačias metrikas kaip `dvc repro`: accuracy 0,7833,
  F1 0,6393.

## GHCR

| | |
|---|---|
| Vaizdas | `ghcr.io/lukasja111/mlops-u1/train:sha-08fbb275` |
| Digest | `sha256:a3023992f65caeda898be68eb242548b77ce9dbd23697779b6d7ee4b19c19b94` |
| Prieiga | vieša: anoniminė registro užklausa grąžina tą patį digest, kind Job'as vaizdą atsisiunčia be prisijungimo |
| Paketas | <https://github.com/users/lukasja111/packages/container/package/mlops-u1%2Ftrain> |
| `org.opencontainers.image.revision` | `08fbb275`: tas pats kaip tag'as ir MLflow `git_commit` |

```bash
docker pull ghcr.io/lukasja111/mlops-u1/train@sha256:a3023992f65caeda898be68eb242548b77ce9dbd23697779b6d7ee4b19c19b94
```

Tag'as nurodo commit'ą, digest'as tiksliai fiksuoja paskelbtą turinį; `latest` nenaudojamas.
