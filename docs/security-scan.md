# Trivy skenavimas

| | |
|---|---|
| Vaizdas | `mlops-u1/train:sha-71249941` |
| Image ID | `sha256:568a3f036f1918d3d20921ad9b11da25cd3be9da7893d4bcebc4c18fe3bf922d` |
| Data | 2026-10-19 |
| Trivy | 0.72.0 |
| OS | Debian 13.7 |
| Pilna ataskaita | [`trivy-train.json`](trivy-train.json) |
| SBOM | [`sbom-train.json`](sbom-train.json) (SPDX 2.3, 146 paketai) |

Komandos yra README 9 žingsnyje („Mokymo Docker vaizdas“). CRITICAL vartas (`--severity CRITICAL --exit-code 1`) kartojamas ir
`scripts/publish.sh` pradžioje, todėl vaizdas su CRITICAL radiniu nepublikuojamas. SBOM yra visų vaizdo paketų sąrašas,
pagal kurį vėliau galima tikrinti naujus CVE be vaizdo atsisiuntimo.

## Rezultatas

- **CRITICAL: 0. HIGH: 44** (8 unikalūs CVE, visi Debian paketuose; nė vienam dar nėra pataisytos versijos). Python
  paketuose radinių nėra.
- **Vartas:** exit code **0**, publikuoti galima.
- Konteineris veikia ne root teisėmis: `docker run --rm --entrypoint id <vaizdas> -u` grąžina `1000`.

## HIGH radinių analizė

| CVE | Paketai | Pataisyta versija | Aktualumas mokymo Job'ui | Sprendimas |
|---|---|---|---|---|
| CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 | util-linux: `bsdutils`, `libblkid1`, `liblastlog2-2`, `libmount1`, `libsmartcols1`, `libuuid1`, `login`, `mount`, `util-linux` | nėra | `mount` pagalbinės programos ir `nsenter`; mokymo procesas jų nekviečia ir veikia kaip UID 1000 be privilegijų | Priimta; pataisa ateis su `apt-get upgrade` perkūrus vaizdą |
| CVE-2026-54369 | `libacl1` | nėra | ACL funkcijos su simbolinėmis nuorodomis; procesas rašo tik į `/app/models` | Priimta |
| CVE-2025-69720 | ncurses: `libncursesw6`, `libtinfo6`, `ncurses-base`, `ncurses-bin` | nėra | Terminalo biblioteka; Job'as veikia be TTY | Priimta |
| CVE-2026-16742 | `libsystemd0`, `libudev1` | nėra | Pažeidžiamas `systemd-homed`, kurio vaizde nėra (yra tik bibliotekos) | Priimta |
| CVE-2026-9538 | `perl-base` (Archive::Tar) | nėra (Debian: fix deferred) | DoS apdorojant tar archyvus; vaizdas jų neapdoroja | Priimta |

Pilnas `mlflow` 3.15.2 vaizde pridėtų du Python HIGH: CVE-2026-69247 (`cryptography` 49.0.0) ir CVE-2026-71211 (`mlflow`
AI Gateway serverio funkcija). Vaizdas diegia `mlflow-skinny`, todėl `cryptography` yra 50.0.2 (pataisyta), o serverio
paketo nėra. Pilnas `mlflow==3.15.2` lieka kūrėjo aplinkoje ir klasterio serveryje, pasiekiamuose tik per `127.0.0.1`.
