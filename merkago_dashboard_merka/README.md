# Merka BI — Merkago Dashboard

Tableaux de bord self-service pour **Odoo 17** — produit **merkago.net**.

Version module : `17.0.2.6.0`

## Multi-version (18 / 19 / 20)

Les builds Apps Store sont générés dans :

`../merkago_dashboard_merka_releases/`

| Série | Version | Zip |
|-------|---------|-----|
| 17.0 | 17.0.2.6.0 | `merkago_dashboard_merka_17.0.zip` |
| 18.0 | 18.0.2.6.0 | `merkago_dashboard_merka_18.0.zip` |
| 19.0 | 19.0.2.6.0 | `merkago_dashboard_merka_19.0.zip` |
| 20.0 | 20.0.2.6.0 | `merkago_dashboard_merka_20.0.zip` |

Rebuild :

```bash
python3 ../merkago_dashboard_merka_releases/build_versions.py
```

Développer **toujours** sur cette source 17, puis regenerer 18/19/20.

## Installation (17)

1. Placer le module dans un addons path (`custom_addons`).
2. Mettre à jour la liste des applications.
3. Installer **Merka BI — Merkago Dashboard**.

## Groupes

| Groupe | Droits |
|--------|--------|
| Administrator | Configuration complète |
| User | Lecture des TB autorisés |
| Restricted | Uniquement les TB explicitement assignés |

## Documentation

- CDC : `CDC.md`
- Releases : `../merkago_dashboard_merka_releases/README.md`
- Support : akremkhelifi07@gmail.com · https://merkago.net

## Licence

OPL-1 — une licence par installation, pas de redistribution.
