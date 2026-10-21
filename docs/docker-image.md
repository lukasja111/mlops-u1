# Mokymo Docker vaizdas

| | |
|---|---|
| Vaizdas | `ghcr.io/lukasja111/mlops-u1/train:sha-08fbb275` |
| Digest | `sha256:a3023992f65caeda898be68eb242548b77ce9dbd23697779b6d7ee4b19c19b94` |
| Image ID | `sha256:90451178305a95902082369da089650c8b139b54286aa274ddd212d055a505d8` |
| Bazė | `python:3.12.14-slim-trixie`, linux/amd64 |
| Commit | `08fbb275`: tag'as, `org.opencontainers.image.revision` ir run'o `git_commit` sutampa |
| Prieiga | vieša: anoniminė registro užklausa grąžina tą patį digest, kind Job'as traukia be prisijungimo |
| Paketas | <https://github.com/users/lukasja111/packages/container/package/mlops-u1%2Ftrain> |

Tag'as nurodo commit'ą, digest'as fiksuoja paskelbtą turinį; `latest` nenaudojamas. 
Kitas commit'as duoda naują tag'ą, tada dydis ir Trivy matuojami iš naujo.

## Dydis

Rootfs 449,68 MB, NFR-11 riba yra `500 MB`. Rootfs yra išpakuotų failų dydis (`du -sx --apparent-size`).

> [!WARNING]
> Docker `.Size` tą patį vaizdą rodo kaip 464,89 MB, nes skaičiuoja kitaip.

- Kur dingsta vieta: bazė 115,67 MB, `/opt/venv` 323,51 MB (didžiausi `scipy`, `pandas`, `sklearn`, `numpy`), `data/processed/` 10,49 MB (įdėta į vaizdą, nes Job'as klasteryje nepasiekia lokalaus DVC remote).

- `mlflow-skinny`: mokymui reikia tik MLflow kliento. Pilnas `mlflow` su tuo pačiu Dockerfile duotų 745,10 MB ir 46 HIGH.
 
- Run'as iš vaizdo (`0a566f99`) davė tas pačias metrikas kaip `dvc repro`: accuracy 0,7833, F1 0,6393.

## Trivy

Skenuota 2026-10-20 su Trivy 0.72.0 (OS Debian 13.7). Komandos README 7 žingsnyje; CRITICAL vartas (`--severity CRITICAL --exit-code 1`) kartojamas ir `scripts/publish.sh`, todėl vaizdas su CRITICAL radiniu nepublikuojamas. Pilna ataskaita [`trivy-train.json`](trivy-train.json), SBOM [`sbom-train.json`](sbom-train.json) (SPDX 2.3, 146 paketai): visų vaizdo paketų sąrašas naujiems CVE tikrinti be vaizdo atsisiuntimo.

- CRITICAL 0, HIGH 44 (8 unikalūs CVE, visi Debian paketuose, nė vienam nėra pataisytos versijos). Python paketuose radinių nėra. Vartas grąžina 0, publikuoti galima.
- Konteineris veikia ne root: `docker run --rm --entrypoint id <vaizdas> -u` grąžina `1000`.

### HIGH radiniai

| CVE | Paketai | Pataisyta versija | Aktualumas mokymo Job'ui | Sprendimas |
|---|---|---|---|---|
| CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 | util-linux: `bsdutils`, `libblkid1`, `liblastlog2-2`, `libmount1`, `libsmartcols1`, `libuuid1`, `login`, `mount`, `util-linux` | nėra | `mount` pagalbinės programos ir `nsenter`; mokymo procesas jų nekviečia ir veikia kaip UID 1000 be privilegijų | Priimta; pataisa ateis su `apt-get upgrade` perkūrus vaizdą |
| CVE-2026-54369 | `libacl1` | nėra | ACL funkcijos su simbolinėmis nuorodomis; procesas rašo tik į `/app/models` | Priimta |
| CVE-2025-69720 | ncurses: `libncursesw6`, `libtinfo6`, `ncurses-base`, `ncurses-bin` | nėra | Terminalo biblioteka; Job'as veikia be TTY | Priimta |
| CVE-2026-16742 | `libsystemd0`, `libudev1` | nėra | Pažeidžiamas `systemd-homed`, kurio vaizde nėra (yra tik bibliotekos) | Priimta |
| CVE-2026-9538 | `perl-base` (Archive::Tar) | nėra (Debian: fix deferred) | DoS apdorojant tar archyvus; vaizdas jų neapdoroja | Priimta |
