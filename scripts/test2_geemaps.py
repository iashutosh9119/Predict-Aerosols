import ee
import geemap

Map = geemap.Map(center=(40, -100), zoom=4)

Map = geemap.Map()
Map.add_basemap("Esri.WorldImagery")
Map.add_basemap("OpenTopoMap")
Map
