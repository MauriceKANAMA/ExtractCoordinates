# Extract Coordinates
<img width="512" height="512" alt="icon" src="https://github.com/user-attachments/assets/214a8c51-9ad4-47d1-b405-b6b6c5ef6490" />


Extension QGIS qui extrait les sommets (nœuds) des couches vecteur de type **points, lignes ou polygones**, et calcule leurs coordonnées en plusieurs systèmes dont le Degrés Minutes Secondes (DMS), Degrés Décimals (DD) et Universal Transverse Mercator (UTM).

## Fonctionnalités

- Extraction de tous les sommets d'une couche de points, de lignes ou de polygones.
- Coordonnées en **degrés, minutes, secondes** (format `27°28'30.12" E`).
- Coordonnées en **degrés décimaux** (WGS 84, EPSG:4326).
- Coordonnées en **UTM** (EPSG:...) adapté.
- Ajout facultatif d'une ou plusieurs colonnes de la couche source.

## Installation

### Depuis le dépôt officiel de QGIS

1. Ouvrez QGIS, puis allez dans **Extensions > Gérer et installer les extensions**.
2. Cherchez `Extract Coordinates`.
3. Cochez la case du plugin, puis cliquez sur **Installer**.

### Installation manuelle

1. Téléchargez le dépôt en cliquant sur **Code > Download ZIP**.
2. Décompressez le fichier, puis copiez le dossier `extract_coordinates` dans :
   `C:\Users\<votre nom>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
3. Redémarrez QGIS et activez le plugin dans le gestionnaire d'extensions.

## Utilisation

1. Cliquez sur l'icône **Extract Coordinates** dans la barre d'outils, ou ouvrez la boîte à outils de traitement (**Ctrl+Alt+T**) et cherchez « Extraire les sommets ».
2. Dans **Couche vecteur**, choisissez une couche de points, de lignes ou de polygones.
3. Dans **Colonnes à ajouter (facultatif)**, cochez les colonnes de la couche que vous voulez retrouver dans le résultat. Vous pouvez laisser ce champ vide.
4. Dans **Sommets extraits**, indiquez le fichier de sortie (par exemple `sommets.gpkg` ou `sommets.xlsx`).
5. Cliquez sur **Exécuter**.

La couche créée s'ajoute automatiquement au projet.

## Colonnes produites

| Colonne | Contenu |
|---|---|
| `id` | Numéro du sommet, de 1 à n |
| `LongitudeDMS` | Longitude en degrés, minutes, secondes (E ou O) |
| `LatitudeDMS` | Latitude en degrés, minutes, secondes (N ou S) |
| `LongitudeDD` | Longitude en degrés décimaux (WGS 84) |
| `LatitudeDD` | Latitude en degrés décimaux (WGS 84) |
| `LongitudeUTM` | Coordonnée Est en UTM 35S (mètres) |
| `LatitudeUTM` | Coordonnée Nord en UTM 35S (mètres) |

Les colonnes choisies à l'étape 3 sont ajoutées à la fin. Si leur nom est déjà utilisé, elles reçoivent le préfixe `attr_`.

## Remarques

- Pour un **polygone**, le sommet de fermeture (qui répète le premier sommet) n'est pas extrait.
- Le format de sortie est celui que vous choisissez (GeoPackage, Shapefile, XLSX, etc.).

## Signaler un problème

Pour signaler un bogue ou proposer une amélioration, ouvrez une demande sur la page **Issues** de ce dépôt.

## Auteur

Maurice KANAMA : mauricekanama1@gmail.com

##
