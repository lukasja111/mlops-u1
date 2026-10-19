# Docker vaizdo dydis

MB = 1 000 000 baitų. **Rootfs**: išpakuotų failų dydis (`du -sx --apparent-size --block-size=1 /`, tas pats metodas
kaip kurso `scripts/week3.py sizes`). Docker `.Size` priklauso nuo image store (čia `overlay2`, nesuspaustas turinys),
todėl su rootfs jo nepainioti.

| Vaizdas | Image ID | Platforma | Bazė | Docker .Size MB | Rootfs MB |
|---|---|---|---|---:|---:|
| `mlops-u1/train:sha-71249941` | `sha256:568a3f036f19` | linux/amd64 | `python:3.12.14-slim-trixie` | 464,85 | 449,63 |

- **NFR-11:** rootfs ≤ 500 MB (kurso 3 savaitės CPU vaizdo tikslas); išmatuota 449,63 MB.
- **Kur dingsta vieta:** bazė 115,88 MB, `/opt/venv` 323,47 MB (didžiausi `scipy`, `pandas`, `sklearn`, `numpy`),
  mokymo duomenys `data/processed/` 10,49 MB: jie įdėti į vaizdą, nes Job'as klasteryje nepasiekia lokalaus DVC remote.
- **Kodėl `mlflow-skinny`:** mokymui reikia tik MLflow kliento. Pilnas `mlflow` su tuo pačiu Dockerfile duotų
  745,10 MB ir 46 HIGH (vietoje 449,63 MB ir 44).
- Vaizdas sukurtas iš commit'o `71249941`; kitas commit'as duoda naują tag'ą ir image ID, tada dydis ir Trivy
  matuojami iš naujo. Run'as iš vaizdo (`f0cbe603`) davė tas pačias metrikas kaip `dvc repro`: accuracy 0,7764,
  F1 0,6298.

## GHCR

| | |
|---|---|
| Vaizdas | `ghcr.io/lukasja111/mlops-u1/train:sha-71249941` |
| Digest | `sha256:14ef4686875870348bc74afe4609db8e497fd6e34429749b66e95b6c45c23ab3` |
| Prieiga | vieša: anoniminė registro užklausa grąžina tą patį digest, kind Job'as vaizdą atsisiunčia be prisijungimo |
| Paketas | <https://github.com/users/lukasja111/packages/container/package/mlops-u1%2Ftrain> |
| `org.opencontainers.image.revision` | `71249941`: tas pats kaip tag'as ir MLflow `git_commit` |

```bash
docker pull ghcr.io/lukasja111/mlops-u1/train@sha256:14ef4686875870348bc74afe4609db8e497fd6e34429749b66e95b6c45c23ab3
```

Tag'as nurodo commit'ą, digest'as tiksliai fiksuoja paskelbtą turinį; `latest` nenaudojamas.
