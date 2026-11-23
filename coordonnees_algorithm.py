# -*- coding: utf-8 -*-
import math

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsCsException,
    QgsFeature, QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterCrs, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingProvider, QgsProject, QgsWkbTypes
)


def to_dms(value, pos_label, neg_label):
    """Convertit des degrés décimaux en format 27°28'30.12" E."""
    hemi = neg_label if value < 0 else pos_label
    total = round(abs(value) * 3600, 2)
    deg = int(total // 3600)
    minutes = int((total - deg * 3600) // 60)
    sec = round(total - deg * 3600 - minutes * 60, 2)
    if sec >= 60:
        sec = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        deg += 1
    return f"{deg}°{minutes:02d}'{sec:05.2f}\" {hemi}"


def sommets_polygone(geom):
    """Retourne les sommets d'un polygone, sans le sommet de fermeture de chaque anneau (trous inclus)."""
    if QgsWkbTypes.isMultiType(geom.wkbType()):
        polygones = geom.asMultiPolygon()
    else:
        polygones = [geom.asPolygon()]
    sommets = []
    for anneaux in polygones:
        for anneau in anneaux:
            sommets.extend(anneau[:-1])
    return sommets


def zone_utm(longitude):
    """Retourne le numéro de zone UTM (1 à 60) d'une longitude en degrés."""
    longitude = min(max(longitude, -179.9999), 179.9999)
    return int((longitude + 180) // 6) + 1


def points_hors_zone(src_crs, crs_proj, extent, ctx):
    """Retourne True si un coin ou le centre de l'étendue ne peut pas être projeté dans crs_proj."""
    transf = QgsCoordinateTransform(src_crs, crs_proj, ctx)
    candidats = [
        QgsPointXY(extent.xMinimum(), extent.yMinimum()),
        QgsPointXY(extent.xMaximum(), extent.yMinimum()),
        QgsPointXY(extent.xMinimum(), extent.yMaximum()),
        QgsPointXY(extent.xMaximum(), extent.yMaximum()),
        QgsPointXY(extent.center()),
    ]
    for p in candidats:
        try:
            r = transf.transform(p)
        except QgsCsException:
            return True
        if not (math.isfinite(r.x()) and math.isfinite(r.y())):
            return True
    return False


def code_epsg_utm(zone, hemisphere_sud):
    """Retourne le code EPSG UTM WGS 84 : 326xx pour le Nord, 327xx pour le Sud."""
    base = 32700 if hemisphere_sud else 32600
    return base + zone


class ExtractionSommetsAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    CHAMP = 'CHAMP'
    CRS_UTM = 'CRS_UTM'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Couche vecteur (points, lignes ou polygones)'),
            [QgsProcessing.SourceType.TypeVectorPoint,
             QgsProcessing.SourceType.TypeVectorLine,
             QgsProcessing.SourceType.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.CHAMP,
            self.tr('Colonnes à ajouter'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Any,
            allowMultiple=True,
            optional=True))
        self.addParameter(QgsProcessingParameterCrs(
            self.CRS_UTM,
            self.tr('Système de coordonnées projeté (en mètres)'),
            defaultValue='EPSG:32735'))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Sommets extraits')))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT))

        noms_champs = self.parameterAsFields(parameters, self.CHAMP, context)
        src_fields = source.fields()
        idx_champs = [src_fields.indexFromName(n) for n in noms_champs
                      if src_fields.indexFromName(n) >= 0]

        ctx = QgsProject.instance().transformContext()
        src_crs = source.sourceCrs()
        if not src_crs.isValid():
            raise QgsProcessingException(
                'La couche sélectionnée n\'a pas de système de coordonnées défini. '
                'Définissez-le dans les propriétés de la couche, puis relancez le traitement.')
        if source.featureCount() == 0 or source.sourceExtent().isNull():
            raise QgsProcessingException(
                'La couche sélectionnée ne contient aucune géométrie exploitable.')
        wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')

        # Système de sortie choisi avec le sélecteur
        crs_proj = self.parameterAsCrs(parameters, self.CRS_UTM, context)
        if not crs_proj.isValid():
            raise QgsProcessingException(
                'Le système de coordonnées choisi n\'est pas valide.')
        if crs_proj.isGeographic():
            raise QgsProcessingException(
                'Le système choisi doit être projeté (en mètres), par exemple une UTM '
                'ou un Lambert. Un système géographique (en degrés) n\'est pas accepté.')
        auth = crs_proj.authid()

        extent = source.sourceExtent()

        # Contrôle général : les données doivent être dans la zone de validité du système choisi
        if points_hors_zone(src_crs, crs_proj, extent, ctx):
            raise QgsProcessingException(
                f'Les données ne sont pas dans la zone de validité du système {auth}. '
                'Choisissez un autre système de coordonnées projeté, puis relancez le traitement.')

        # Contrôle pour les UTM WGS 84 : toute l'étendue doit être dans la zone choisie
        try:
            code_utm = int(auth.split(':')[1])
        except (IndexError, ValueError):
            code_utm = 0
        if code_utm // 100 in (326, 327):
            zone = code_utm % 100
            hemi_sud = (code_utm // 100 == 327)
            to_geo = QgsCoordinateTransform(src_crs, wgs84, ctx)
            bbox = to_geo.transformBoundingBox(extent)

            zone_min = zone_utm(bbox.xMinimum())
            zone_max = zone_utm(bbox.xMaximum())
            if zone_min != zone_max:
                raise QgsProcessingException(
                    f'Les données s\'étendent sur plusieurs zones UTM (de la zone {zone_min} '
                    f'à la zone {zone_max}). Une seule zone UTM ne peut pas convenir à '
                    f'l\'ensemble : choisissez un système projeté qui couvre toute la zone '
                    f'de travail, ou extrayez les données par zone.')

            if zone_min != zone:
                raise QgsProcessingException(
                    f'Attention : les données se trouvent dans la zone {zone_min}, '
                    f'et non dans la zone {zone}. Les coordonnées UTM seront déformées.')

            if (bbox.yMinimum() < 0) != hemi_sud or (bbox.yMaximum() < 0) != hemi_sud:
                hemi_txt = 'Sud' if hemi_sud else 'Nord'
                raise QgsProcessingException(
                    f'Les données ne sont pas toutes dans l\'hémisphère {hemi_txt} '
                    f'de la projection choisie. Choisissez la bonne zone, ou extrayez '
                    f'les données par hémisphère.')

        vides = sum(1 for f in source.getFeatures()
                    if not f.hasGeometry() or f.geometry().isEmpty())
        if vides > 0:
            raise QgsProcessingException(
                f'{vides} entité(s) vide(s) ou sans géométrie. '
                'Corrigez ou supprimez-les, puis relancez le traitement.')

        fields = QgsFields()
        fields.append(QgsField('id', QVariant.Int))
        fields.append(QgsField('LongitudeDMS', QVariant.String))
        fields.append(QgsField('LatitudeDMS', QVariant.String))
        fields.append(QgsField('LongitudeDD', QVariant.Double))
        fields.append(QgsField('LatitudeDD', QVariant.Double))
        fields.append(QgsField('LongitudeUTM', QVariant.Double))
        fields.append(QgsField('LatitudeUTM', QVariant.Double))

        for idx in idx_champs:
            champ_def = QgsField(src_fields.field(idx))
            nom_sortie = champ_def.name()
            if nom_sortie in fields.names():
                nom_sortie = 'attr_' + nom_sortie
            champ_def.setName(nom_sortie)
            fields.append(champ_def)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields,
            QgsWkbTypes.Type.Point, src_crs)
        if sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT))

        to_wgs = QgsCoordinateTransform(src_crs, wgs84, ctx)
        to_proj = QgsCoordinateTransform(src_crs, crs_proj, ctx)
        feedback.pushInfo(f'Système de projection utilisé : {auth}')

        total = source.featureCount() or 1
        compteur = 0

        for current, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()

            if geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry:
                points = sommets_polygone(geom)
            else:
                points = [QgsPointXY(v) for v in geom.vertices()]

            for p_src in points:
                p_wgs = to_wgs.transform(p_src)
                p_proj = to_proj.transform(p_src)

                compteur += 1

                attributs = [
                    compteur,
                    to_dms(p_wgs.x(), 'E', 'O'),
                    to_dms(p_wgs.y(), 'N', 'S'),
                    p_wgs.x(),
                    p_wgs.y(),
                    p_proj.x(),
                    p_proj.y(),
                ]
                for idx in idx_champs:
                    attributs.append(feat.attribute(idx))

                out = QgsFeature(fields)
                out.setGeometry(QgsGeometry.fromPointXY(p_src))
                out.setAttributes(attributs)
                sink.addFeature(out, QgsFeatureSink.SinkFlag.FastInsert)

            feedback.setProgress(int(100 * current / total))

        return {self.OUTPUT: dest_id}

    def tr(self, message):
        """Retourne la traduction du message."""
        return QCoreApplication.translate('ExtractionSommetsAlgorithm', message)

    def name(self):
        return 'extraction_sommets'

    def displayName(self):
        return self.tr('Extraire les sommets (points, lignes, polygones)')

    def group(self):
        return self.tr('Extraction de coordonnées')

    def groupId(self):
        return 'extraction_coordonnees'

    def shortHelpString(self):
        return self.tr(
            'Extrait les sommets (nœuds) des points, lignes et polygones.<br>'
            'Calcule leurs coordonnées en WGS 84 (DMS et degrés décimaux) '
            'et dans le système projeté choisi (en mètres).<br><br>'
            '<b>Colonnes à ajouter</b> (facultatif) : recopie une ou plusieurs colonnes '
            'de la couche source dans la table des sommets.<br><br>'
            '<b>Système de coordonnées projeté</b> : choisissez le système avec le sélecteur '
            '(icône à droite du champ). Les systèmes géographiques (en degrés) ne sont pas acceptés. '
            'Si les données ne sont pas dans la zone de validité du système, ou si une UTM ne couvre '
            'pas toutes les données, le traitement s\'arrête avec un message et aucune couche n\'est créée.<br><br>'
        )

    def createInstance(self):
        return ExtractionSommetsAlgorithm()


class CoordinatesProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(ExtractionSommetsAlgorithm())

    def id(self):
        return 'extraction_coordonnees'

    def name(self):
        return 'Extraction de coordonnées'

    def longName(self):
        return self.name()
