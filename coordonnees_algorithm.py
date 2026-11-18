# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingProvider, QgsProject, QgsWkbTypes
)


def to_dms(value, pos_label, neg_label):
    """Convertit des degrés décimaux en format 27°28'30.12" E (logique du modèle)."""
    hemi = neg_label if value < 0 else pos_label
    t = round(abs(value) * 3600, 2)
    deg = int(t // 3600)
    minutes = int((t - deg * 3600) // 60)
    sec = round(t - deg * 3600 - minutes * 60, 2)
    return f"{deg}°{minutes:02d}'{sec:05.2f}\" {hemi}"


class ExtractionSommetsAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            'Couche vecteur (points, lignes ou polygones)',
            [QgsProcessing.TypeVectorPoint,
             QgsProcessing.TypeVectorLine,
             QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Sommets extraits'))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT))

        fields = QgsFields()
        fields.append(QgsField('id', QVariant.Int))
        fields.append(QgsField('Longitude DMS', QVariant.String))
        fields.append(QgsField('Latitude DMS', QVariant.String))
        fields.append(QgsField('Longitude DD', QVariant.Double))
        fields.append(QgsField('Latitude DD', QVariant.Double))
        fields.append(QgsField('Longitude UTM', QVariant.Double))
        fields.append(QgsField('Latitude UTM', QVariant.Double))

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
                # (identique au premier sommet de l'anneau).
                if is_polygon:
                    key = (round(x, 9), round(y, 9))
                    if key in seen:
                        continue
                    seen.add(key)

                p_src = QgsPointXY(x, y)
                p_wgs = to_wgs.transform(p_src)
                p_utm = to_utm.transform(p_src)

                out = QgsFeature(fields)
                out.setGeometry(QgsGeometry.fromPointXY(p_src))
                out.setAttributes([
                    feat.id(),
                    to_dms(p_wgs.x(), 'E', 'O'),
                    to_dms(p_wgs.y(), 'N', 'S'),
                    p_wgs.x(),
                    p_wgs.y(),
                    p_utm.x(),
                    p_utm.y(),
                ])
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
                'et calcule leurs coordonnées en WGS 84 (degrés minutes secondes (DMS) et degrés décimaux (DD) '
                'et en UTM.')

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