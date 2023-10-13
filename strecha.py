
import os
import sys
import argparse
import subprocess
from qgis import processing
from osgeo import gdal
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsCoordinateReferenceSystem

# Parsovaní argumentů předaných z bash/cmd skriptu
#parser = argparse.ArgumentParser(description='QGIS Processing Script with Parameters')
#parser.add_argument('--DEM_PATH', type=str, help='Vstupní DEM v TIFu', required=True)
#parser.add_argument('--DXF_PATH', type=str, help='Vstupní obvod v DXF formátu', required=True)
#parser.add_argument('--OUTPUT_DIR', type=str, help='Výstupni adresář, kde budou uloženy výsledky i mezivýsledky. Pokud neexistuje, vytvoří se.', required=True)

# Zpracování argumentů
#args = parser.parse_args()
#dxf_file_path = args.DXF_PATH
#raster_file_path = args.DEM_PATH
#output_dir = args.OUTPUT_DIR
dxf_file_path = "/home/linduska/strecha/strecha3/obvod.dxf"
raster_file_path = "/home/linduska/strecha/strecha3/dem.tif"
output_dir = "/home/linduska/strecha/strecha3/output"

# Vytvoření výstupního adresáře
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

####### Definice funkcí #######

def remove_all_layers_from_project():
    # Získání seznamu všech vrstev v projektu
    layers = QgsProject.instance().mapLayers().values()

    # Odstranění všech vrstev z projektu
    for layer in layers:
        QgsProject.instance().removeMapLayer(layer.id())

def display_raster_layer(layer_path, layer_name):
    # Vytvoření QgsRasterLayer
    raster_layer = QgsRasterLayer(layer_path, layer_name)
    
    # Kontrola platnosti vrstvy
    if not raster_layer.isValid():
        print("Chyba: Rastrová vrstva {} se nepodařila načíst.".format(layer_path))
    else:
        # Přidání vrstvy do projektu v QGIS
        QgsProject.instance().addMapLayer(raster_layer)

        print("Rastrová vrstva {} byla úspěšně načtena".format(layer_path))

def display_vector_layer(layer_path, layer_name):
    # Vytvoření QgsVectorLayer
    vector_layer = QgsVectorLayer(layer_path, layer_name, 'ogr')
    
    # Kontrola platnosti vrstvy
    if not vector_layer.isValid():
        print("Chyba: Vektorová vrstva {} se nepodařila načíst.".format(layer_path))
    else:
        # Přidání vrstvy do projektu v QGIS
        QgsProject.instance().addMapLayer(vector_layer)

        print("Vektorová vrstva {} byla úspěšně načtena".format(layer_path))

def convert_dxf_to_shapefile(dxf_file_path, mask_layer_path):
    # Příkaz pro spuštění ogr2ogr
    command = [
        'ogr2ogr',
        '-f', 'ESRI Shapefile',  # Formát výstupního souboru (SHP)
        '-s_srs', 'EPSG:5514',  # Zdrojový CRS ('EPSG:5514')
        '-t_srs', 'EPSG:5514',  # Cílový CRS (EPSG:5514)
        mask_layer_path,         # Cílový soubor SHP
        dxf_file_path,           # Vstupní DXF soubor
        '-nlt', 'POLYGON',       # Typ geometrie (polygony)
        '-skipfailures'         # Přeskočit chyby a pokračovat v převodu
    ]
    # Samotná konverze
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        print(f"Převod z DXF na SHP byl úspěšně dokončen. Výstupní soubor: {mask_layer_path}")
    except subprocess.CalledProcessError as e:
        print(f"Chyba při převodu z DXF na SHP: {e.stderr}")
    except Exception as ex:
        print(f"Nastala neočekávaná chyba: {str(ex)}")

def clip_raster_by_vector(input_raster_path, input_vector_path, output_raster_path, output_name, crs):
    # Ořezání vstupního rastru pomocí vektorové masky
    try:
        crs = QgsCoordinateReferenceSystem(crs)

        processing.run("gdal:cliprasterbymasklayer", {
            'INPUT': input_raster_path,
            'MASK': input_vector_path,
            'TARGET_CRS': crs,
            'SOURCE_CRS': crs,
            'CROP_TO_CUTLINE': True,
            'OUTPUT': output_raster_path
        })
        print(f"Oříznutý rastrový soubor byl uložen do souboru: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)

    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def calculate_median_zonal_statistics(clipped_raster_path, mask_vector_path, output_gpkg_path, output_name, band=1):
    try:
        # Spuštění zonální statistiky
        processing.run('native:zonalstatisticsfb', {
            'INPUT_RASTER': clipped_raster_path,
            'RASTER_BAND': band,
            'INPUT': mask_vector_path,
            'COLUMN_PREFIX': '_',
            'STATISTICS': [3],  # Pro medián
            'OUTPUT': output_gpkg_path
        })
        print(f"Medián zonální statistiky byl uložen do souboru: {output_gpkg_path}")
        
        # Vytvoření QgsVectorLayer
        output_gpkg = QgsVectorLayer(output_gpkg_path, output_name)
        
        # Kontrola platnosti vrstvy
        if not output_gpkg.isValid():
            print("Chyba: Vektorová vrstva {} se nepodařila načíst.".format(output_gpkg_path))
        else:
            # Přidání vrstvy do projektu v QGIS
            QgsProject.instance().addMapLayer(output_gpkg)

            print("Vektorová vrstva {} byla úspěšně načtena".format(output_gpkg_path))

        # Získání hodnoty mediánu z výstupní vrstvy
        features = output_gpkg.getFeatures()
        median_value = 0
        for feature in features:
            median_value = feature['_median']  # Název sloupce s mediánem
            print(f'Medián: {median_value}')
        return median_value

    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def run_raster_calculator(expression, input_raster_layer, output_raster_path, output_name):
    try:
        # Spuštění QGIS Raster Calculator
        processing.run('qgis:rastercalculator', {
        'EXPRESSION': expression,
        'LAYERS': input_raster_layer,
        'OUTPUT': output_raster_path
        })
        print(f"Přepočtený rastr byl uložen do souboru: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)

    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def run_rank_filter(input_raster_path, output_raster_path, radius=2, rank=50, kernel_type=0):
    try:
        # Spuštění funkce Rank Filter
        processing.run("sagang:rankfilter", {
            'INPUT': input_raster_path,
            'KERNEL_TYPE': kernel_type,
            'KERNEL_RADIUS': radius,
            'RANK': rank,
            'RESULT': output_raster_path
        })
        print(f"Rank Filter byl úspěšně aplikován na rastr a výsledek byl uložen do souboru: {output_raster_path}")

    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def convert_SAGA_type_to_GeoTIFF(input_raster_path, output_raster_path, output_name):
    try:
        # Spuštění konverze
        processing.run("gdal:translate", {
            'INPUT': input_raster_path,
            'OPTIONS': 'COMPRESS=DEFLATE',
            'DATA_TYPE': 6,  # Data type 5 odpovídá Float32
            'OUTPUT': output_raster_path
        })
        print(f"Rastr byl úspečně zkonvertován na GeoTIFF v cestě: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)

    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def run_slope_analysis(input_raster_path, output_raster_path, output_name, band=1):
    try:
        # Spuštění funkce "Slope"
        processing.run("qgis:slope", {
            'INPUT': input_raster_path,
            'BAND': band,
            'OUTPUT': output_raster_path
        })
        print(f"Analýza sklonu byla úspěšně provedena a výsledek byl uložen do souboru: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)
    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def convert_raster_to_8bit(input_raster_path, output_raster_path, output_name, nodata_value=255):
    try:
        # Spuštění funkce "Translate"
        processing.run("gdal:translate", {
            'INPUT': input_raster_path,
            'DATA_TYPE': 1,  # 1 odpovídá 8bit
            'NODATA': nodata_value,
            'OUTPUT': output_raster_path
        })
        print(f"Rastrový soubor byl úspěšně konvertován na 8 bitů a uložen do souboru: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)
    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def rescale_raster_to_0_255(input_raster_path, output_raster_path, output_name):
    try:
        # Spuštění funkce "Rescale Raster"
        processing.run("native:rescaleraster", {
            'INPUT': input_raster_path,
            'BAND': 1,
            'MAXIMUM': 255,
            'MINIMUM': 0,
            'NODATA': None,
            'OUTPUT': output_raster_path
        })
        print(f"Rastrový soubor byl úspěšně reskalován na rozsah od 0 do 255 a uložen do souboru: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)
    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

#######  Cesty k výstupním souborům ####### 
mask_path = os.path.join(output_dir, 'obvod.shp')
clipped_dem_path = os.path.join(output_dir, 'clipped_dem.tif') # DEM clipped 
stats_path = os.path.join(output_dir, 'stats.gpkg') # Statistika s medianem
normalized_dem_path = os.path.join(output_dir, 'normalized_dem.tif')  # normalized clipped DEM 
filtered_dem_path = os.path.join(output_dir, 'filtered_dem.sdat')  # filtered DEM v puvodnim formatu SAGY
filtered_dem_gt_path = os.path.join(output_dir, 'filtered_dem.tif') # filtered DEM (GeoTIFF)
slope_path = os.path.join(output_dir, 'slope.tif') # Slope
slope_8bit_path = os.path.join(output_dir, 'slope_8bit.tif') # Slope (8 bit)
rescaled_dem_path = os.path.join(output_dir, 'rescaled_dem.tif') # DEM rescaled
dem_8bit_path = os.path.join(output_dir, 'dem_8bit.tif') # DEM (8 bit)

## Inicializace QGIS aplikace
#qgs = QgsApplication([], False)
#qgs.initQgis()
#
#qgs.setPrefixPath("/usr/bin/qgis", True)
#sys.path.append('/usr/bin/python3') 

# Odstraneni vrstev z projektu
#remove_all_layers_from_project()

# Konverze DXF na SHAPEFILE
# Příkaz pro spuštění ogr2ogr
convert_dxf_to_shapefile(dxf_file_path, mask_path)

# Zobrazeni vrstvy obvodu v QGISu
display_vector_layer(mask_path, "Obvod")

# Zobrazeni vrstvy DEM v QGISu
display_raster_layer(raster_file_path, "DEM")

# Nastavení souřadnicového systému (CRS) pro vrstvu
crs = QgsCoordinateReferenceSystem("EPSG:5514") 

# Oříznutí DEMu, aby se počítalo jenom v obvodu daném DXF souborem
clip_raster_by_vector(raster_file_path, mask_path, clipped_dem_path, "Clipped_DEM", crs)

# Výpočet mediánu pro oříznutý DEM
median_value = calculate_median_zonal_statistics(clipped_dem_path, mask_path, stats_path, "Zonal_stats")

# Výpočet normalizovaného DEMu
expression = f'Clipped_DEM@1" - {median_value}'
run_raster_calculator(expression, clipped_dem_path, normalized_dem_path, "Normalized_DEM")

# Filtrace DEMu
run_rank_filter(normalized_dem_path, filtered_dem_path)

# Převod SAGA formátu rastru na GeoTIFF, aby mohl být zobrazen v QGISu
convert_SAGA_type_to_GeoTIFF(filtered_dem_path, filtered_dem_gt_path, "Filtered_DEM")

# Výpočet slope analýzy
run_slope_analysis(filtered_dem_gt_path, slope_path, "Slope")

# Konverze slope na 8bit
convert_raster_to_8bit(slope_path, slope_8bit_path, "Slope_8bit")

# Rescalování filtrovaného DEM na hodnoty do 0 do 255
rescale_raster_to_0_255(filtered_dem_gt_path, rescaled_dem_path, "Rescaled_DEM")

# Konverze DEMu na 8bit
convert_raster_to_8bit(rescaled_dem_path, dem_8bit_path, "Rescaled_DEM_8bit")