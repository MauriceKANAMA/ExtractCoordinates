# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingProvider, QgsProject, QgsWkbTypes
)


def to_dms(value, pos_label, neg_label):
    """Convertit des degrés décimaux en format 27°28'30.12\" E (logique du modèle)."""
    hemi = neg_label if value < 0 else pos_label
    t = round(abs(value) * 3600, 2)
    deg = int(t // 3600)
    minutes = int((t - deg * 3600) // 60)
    sec = round(t - deg * 3600 - minutes * 60, 2)
    return f"{deg}°{minutes:02d}'{sec:05.2f}\" {hemi}"


class ExtractionSommetsAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    CHAMP = 'CHAMP'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            'Couche vecteur (points, lignes ou polygones)',
            [QgsProcessing.TypeVectorPoint,
             QgsProcessing.TypeVectorLine,
             QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.CHAMP,
            'Colonnes à ajouter',
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Any,
            allowMultiple=True,
            optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Sommets extraits'))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT))

        noms_champs = self.parameterAsFields(parameters, self.CHAMP, context)
        src_fields = source.fields()
        idx_champs = [src_fields.indexFromName(n) for n in noms_champs
                      if src_fields.indexFromName(n) >= 0]

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
            QgsWkbTypes.Point, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT))

        ctx = QgsProject.instance().transformContext()
        src_crs = source.sourceCrs()
        to_wgs = QgsCoordinateTransform(
            src_crs, QgsCoordinateReferenceSystem('EPSG:4326'), ctx)
        to_utm = QgsCoordinateTransform(
            src_crs, QgsCoordinateReferenceSystem('EPSG:32735'), ctx)

        total = source.featureCount() or 1
        compteur = 0

        for current, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue

            is_polygon = geom.type() == QgsWkbTypes.PolygonGeometry
            seen = set()

            for i in range(geom.constGet().nCoordinates()):
                v = geom.vertexAt(i)
                x, y = v.x(), v.y()

                # Pour les polygones, on ignore le sommet de fermeture
                if is_polygon:
                    key = (round(x, 9), round(y, 9))
                    if key in seen:
                        continue
                    seen.add(key)

                p_src = QgsPointXY(x, y)
                p_wgs = to_wgs.transform(p_src)
                p_utm = to_utm.transform(p_src)

                compteur += 1

                attributs = [
                    compteur,
                    to_dms(p_wgs.x(), 'E', 'O'),
                    to_dms(p_wgs.y(), 'N', 'S'),
                    p_wgs.x(),
                    p_wgs.y(),
                    p_utm.x(),
                    p_utm.y(),
                ]
                for idx in idx_champs:
                    attributs.append(feat.attribute(idx))

                out = QgsFeature(fields)
                out.setGeometry(QgsGeometry.fromPointXY(p_src))
                out.setAttributes(attributs)
                sink.addFeature(out, QgsFeatureSink.FastInsert)

            feedback.setProgress(int(100 * current / total))

        return {self.OUTPUT: dest_id}

    def name(self):
        return 'extraction_sommets'

    def displayName(self):
        return 'Extraire les sommets (points, lignes, polygones)'

    def group(self):
        return 'Extraction de coordonnées'

    def groupId(self):
        return 'extraction_coordonnees'

    def shortHelpString(self):
        return ('Extrait les sommets (nœuds) des points, lignes et polygones '
                'et calcule leurs coordonnées en WGS 84 (degrés décimaux et DMS) '
                'et en UTM 35S (EPSG:32735). Une colonne de la couche source '
                'peut être ajoutée facultativement afin de mieux se retrouver en ce qui concerne les points de la couche.')

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
