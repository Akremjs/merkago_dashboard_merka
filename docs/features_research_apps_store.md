# Inventaire fonctionnalités (recherche Apps Store publique)

**Date :** 18/10/2026  
**Sources publiques :**
- [Ksolves India Ltd. — catalogue](https://apps.odoo.com/apps/modules/browse?author=Ksolves%20India%20Ltd.)
- [Dashboard Ninja with AI 17.0](https://apps.odoo.com/apps/modules/17.0/ks_dashboard_ninja)
- [Dashboard Ninja with AI 19.0](https://apps.odoo.com/apps/modules/19.0/ks_dashboard_ninja)
- Advanced Dashboard Ninja with AI 17.0 (`ks_dn_advance`)

Ce document liste des **capacités produit annoncées publiquement** pour inspirer la roadmap `merkago_dashboard_merka`.  
Aucun code tiers n’est repris. PI 100 % Merkago.

---

## A. Catalogue éditeur (81 apps) — apps liées au reporting

| App | Prix relevé | Angle |
|-----|-------------|-------|
| Dashboard Ninja with AI | ~580–615 USD | Moteur dashboards + IA |
| Advanced Dashboard Ninja with AI | ~746 USD | Extension (PDF mail, SQL KPI…) |
| Account Dashboard Ninja | ~611 USD | Pack compta |
| CRM Dashboard Ninja | ~611 USD | Pack CRM |
| ReportMate | ~245 USD | Rapports custom / requête |
| List View Manager | ~191 USD | Listes avancées |
| Access Manager Ninja | ~323 USD | Droits fins |

---

## B. Fonctionnalités Dashboard Ninja (fiche 17/19)

### Visualisations (17 types annoncés)
1. Tuile (Tile / KPI)  
2. Courbe (Line)  
3. Liste (List) — 2 styles (groupé / non groupé)  
4. Barres verticales  
5. Barres horizontales  
6. Aires (Area)  
7. To-do  
8. Aires polaires (Polar Area)  
9. Camembert (Pie)  
10. Anneau (Doughnut)  
11. Fleur (Flower)  
12. Entonnoir (Funnel)  
13. Radial  
14. Radar  
15. Nuage de points (Scatter)  
16. Bullet chart  
17. Carte (Map)

### Création & layout
- Design layout : resize, drag & drop, reposition, rename  
- Switch Layout (changer le type de graphique sans perdre les données)  
- Instant Edit Mode  
- Multi-color themes (4 thèmes + palette)  
- Layouts / icônes de tuiles  
- Responsive (mobile / tablette / desktop)  
- Bookmark / favoris  
- Page d’accueil utilisateur (personnalisation / configuration)  
- RTL  

### Données & filtres
- Tout modèle Odoo  
- Domaine + Group By + Limit + Sort  
- 20 filtres de date prédéfinis + période custom  
- Variables dynamiques `%UID`, `%MYCOMPANY`  
- Drill-down / drill-up  
- Streaming / refresh temps réel ou intervalle  
- Import Excel / CSV → graphiques  

### IA
- Générer des items avec IA  
- Générer items par mot-clé  
- Générer un dashboard complet depuis un modèle  
- Explication IA d’un graphique  
- Clé API via Settings (e-mail validé)  

### Collaboration & export
- Chat interne par item (Discuss / canal dédié + inbox)  
- Download item : Excel, CSV, PDF, PNG  
- Export / import dashboard ou item (instances)  

### Packs & droits
- 5 dashboards prédéfinis payants : Sales, CRM, Account, Inventory, POS  
- Access control (admin / user / restricted)  
- Multi-société (via filtres)  

---

## C. Fonctionnalités Advance (fiche `ks_dn_advance` 17.0)

- **Custom SQL Query** : combiner plusieurs modèles, stacked charts, filtre date dynamique  
- **Sources externes** : PostgreSQL / MySQL + API externe (beta)  
- **Print Dashboard PDF** : capture complète haut→bas  
- **Send Email** : envoi snapshot PDF aux destinataires présélectionnés  

---

## D. Mapping → Merkago Dashboard Merka

| Capacité publique | Statut Merkago | Priorité |
|-------------------|----------------|----------|
| Tuile KPI + tendance + objectif | Fait (v1.1 UI) | — |
| Bar / Line / Area / Pie / Doughnut | Fait (Chart.js) | — |
| Liste | Partiel | M |
| Layout drag & drop | Non | M |
| Switch Layout | Non | S |
| Filtres date avancés | Partiel | M |
| %UID / %MYCOMPANY | Partiel (domaine) | M |
| Export/import JSON | Fait | — |
| Packs Sales/CRM/Account/Stock | Fait (assistant) | — |
| Pack POS | Non | S |
| Export Excel/CSV/PDF/PNG | Non | M |
| Drill-down multi-niveau | Partiel (ouvre records) | S |
| Refresh auto / streaming | Non | S |
| Excel/CSV → chart | Non | S |
| Favoris / homepage | Non | S |
| Chat item | Non | C |
| IA generate / explain | Param IA off only | S |
| Themes multi-couleur | Un thème dark analytics | S |
| Instant Edit | Non | C |
| RTL | Non | S |
| Horizontal bar / funnel / radar / scatter / bullet / map / polar / flower / todo | Non | 1.2 |
| PDF mail planifié | Non | 1.1 |
| SQL sandbox KPI | Non | 1.2 |
| Alertes seuil | Non | 1.1 |
| Mode TV / kiosk | Non | 1.1 |

---

## E. Next features recommandées (ordre)

1. **Export PNG/PDF/Excel** depuis chaque carte  
2. **Barres horizontales + funnel + radar**  
3. **Filtre date global** sur le dashboard (bandeau)  
4. **Switch Layout** 1 clic  
5. **Refresh auto** (30s / 60s / 5 min)  
6. **Drag & drop layout** (gridstack-like)  
7. **Pack POS + Website**  
8. **Alertes + envoi PDF mail**  
9. **IA optionnelle** (fournisseur au choix, off par défaut)  
