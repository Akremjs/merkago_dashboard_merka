# Merka BI — Odoo 18.0

Généré depuis `merkago_dashboard_merka` (17.0) via `build_versions.py`.

## Adaptations 18.0

| Élément | Changement |
|---------|------------|
| `__manifest__.py` | version `18.0.2.7.0` |
| Vues XML | `<tree>` → `<list>` |
| Form chatter | `<chatter/>` (remplace `oe_chatter`) |
| `hooks.py` | `post_init_hook(env)` (plus `cr, registry`) |

## Installation

1. Copier le dossier `merkago_dashboard_merka` dans les addons Odoo 18.0
2. Mettre à jour la liste des apps
3. Installer **Merka BI — Merkago Dashboard**

## Packaging Apps Store

```bash
cd 18.0
zip -r merkago_dashboard_merka_18.0.zip merkago_dashboard_merka \
  -x '*/__pycache__/*' '*.pyc' '*/.git/*'
```

## Tests recommandés

- [ ] Install à froid
- [ ] Upgrade depuis vide
- [ ] Ouvrir dashboard + chat IA
- [ ] Mode TV / Story
- [ ] Export Excel / PDF
- [ ] Création pack auto (Ventes/CRM si modules présents)

## Notes série

- **18.0** : list views + hooks env obligatoires
- **19.0** : même base 18 ; valider assets OWL / Chart.js sur instance réelle
- **20.0** : même base 19 ; revalider `web.chartjs_lib` et bus_service avant publication
