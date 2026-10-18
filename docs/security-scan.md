# Trivy skenavimas

| | |
|---|---|
| Vaizdas | `mlops-u1/train:sha-0a26641f` |
| Image ID | `sha256:4fbf02538b4fbaa211188f794a2eeb65f96d6e09b9fa9f14704890effeb68ccc` |
| Data | 2026-10-19 |
| Trivy | 0.72.0 |
| OS | Debian 13.7 |
| Pilna ataskaita | [`trivy-train.json`](trivy-train.json) |
| SBOM | [`sbom-train.json`](sbom-train.json) (SPDX 2.3, 146 paketai) |

```bash
trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output docs/trivy-train.json <vaizdas>
trivy image --scanners vuln --severity CRITICAL --exit-code 1 <vaizdas>
trivy image -f spdx-json -o docs/sbom-train.json <vaizdas>
```

Antra komanda yra vartas: ji kartojama ir `scripts/publish.sh` pradžioje, todėl vaizdas su CRITICAL radiniu
nepublikuojamas. Trečia sukuria SBOM, visų vaizdo paketų sąrašą, pagal kurį vėliau galima tikrinti naujus CVE be
vaizdo atsisiuntimo.

## Rezultatas

- **CRITICAL: 0. HIGH: 44** (8 unikalūs CVE, visi Debian paketuose). Python paketuose radinių nėra.
- **Vartas**: exit code **0**, publikuoti galima.
- Nė vienam HIGH dar nėra pataisytos Debian versijos.

## HIGH radinių analizė

| CVE | Paketai | Pataisyta versija | Aktualumas mokymo Job'ui | Sprendimas |
|---|---|---|---|---|
| CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 | util-linux: `bsdutils`, `libblkid1`, `liblastlog2-2`, `libmount1`, `libsmartcols1`, `libuuid1`, `login`, `mount`, `util-linux` | nėra | `mount` pagalbinės programos ir `nsenter`; mokymo procesas jų nekviečia ir veikia kaip UID 1000 be privilegijų | Priimta; pataisa ateis su `apt-get upgrade` perkūrus vaizdą |
| CVE-2026-54369 | `libacl1` | nėra | ACL funkcijos su simbolinėmis nuorodomis; procesas rašo tik į `/app/models` | Priimta |
| CVE-2025-69720 | ncurses: `libncursesw6`, `libtinfo6`, `ncurses-base`, `ncurses-bin` | nėra | Terminalo biblioteka; Job'as veikia be TTY | Priimta |
| CVE-2026-16742 | `libsystemd0`, `libudev1` | nėra | Pažeidžiamas `systemd-homed`, kurio vaizde nėra (yra tik bibliotekos) | Priimta |
| CVE-2026-9538 | `perl-base` (Archive::Tar) | nėra (Debian: fix deferred) | DoS apdorojant tar archyvus; vaizdas jų neapdoroja | Priimta |

## Python paketai

Pilnas `mlflow` 3.15.2 vaizde pridėtų du HIGH: CVE-2026-69247 (`cryptography` 49.0.0, nes `mlflow` riboja
`cryptography<50`; pataisyta 50.0.0) ir CVE-2026-71211 (`mlflow` 3.15.2, AI Gateway serverio funkcija). Vaizdas diegia
`mlflow-skinny`, todėl `cryptography` patenka per databricks-sdk → google-auth kaip 50.0.2 (pataisyta), o `mlflow`
serverio paketo vaizde nėra. Kurso fiksuotas `mlflow==3.15.2` lieka kūrėjo aplinkoje ir klasterio serveryje, kurie
pasiekiami tik per `127.0.0.1`.

Konteineris veikia ne root teisėmis: `docker run --rm --entrypoint id <vaizdas> -u` grąžina `1000`.
