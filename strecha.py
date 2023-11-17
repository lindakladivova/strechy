
import os
import subprocess
from qgis import processing
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsCoordinateReferenceSystem

######################## VSTUPY (je treba zmenit) ###############################
dxf_file_path = "/home/linduska/strecha/strecha1/obvod.dxf"
ortofoto_path = "/home/linduska/strecha/strecha1/ortofoto.tif"
raster_file_path = "/home/linduska/strecha/strecha1/dem.tif"
tir_file_path = "/home/linduska/strecha/strecha1/tir.tif"
output_dir = "/home/linduska/strecha/strecha1/output"

#################################################################################

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

def run_resampling_filter(input_raster_path, output_raster_path_lopass, output_raster_path_hipass, scale=10):
    try:
        # Spuštění funkce Resampling Filter
        processing.run("sagang:resamplingfilter", {
            'GRID': input_raster_path,
            'SCALE': scale,
            'LOPASS': output_raster_path_lopass,
            'HIPASS': output_raster_path_hipass
        })
        print(f"Resampling Filter byl úspěšně aplikován na rastr a výsledek byl uložen do souborů: {output_raster_path_lopass} a {output_raster_path_hipass}")

    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")       

def convert_SAGA_type_to_GeoTIFF(input_raster_path, output_raster_path, output_name):
    try:
        # Spuštění konverze
        processing.run("gdal:translate", {
            'INPUT': input_raster_path,
            'OPTIONS': 'COMPRESS=DEFLATE',
            'DATA_TYPE': 6,  # Data type 6 odpovídá UInt16
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

def select_bands(input_raster_path, output_raster_path, output_name, additional_params):
    try:
        # Spuštění funkce "Translate"
        processing.run("gdal:translate", {
            'INPUT': input_raster_path,
            'EXTRA': additional_params,
            'OUTPUT': output_raster_path
        })
        print(f"Rastrový soubor byl úspěšně uložen pouze s vybranými bandy do souboru: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)
    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")

def merge_rasters(input_rasters, output_raster_path, output_name):
    try:
        # Spuštění funkce "Merge"
        processing.run("gdal:merge", {
            'INPUT': input_rasters,
            'SEPARATE' : True,
            'DATA_TYPE': 0,  # 0 odpovídá 8bit
            'OUTPUT': output_raster_path
        })
        print(f"Rastrový soubor byl úspěšně uložen do souboru: {output_raster_path}")
        display_raster_layer(output_raster_path, output_name)
    except Exception as e:
        print(f"Neočekávaná chyba: {str(e)}")


#######  Cesty k výstupním souborům ####### 
rgb_path = os.path.join(output_dir, 'ortofoto_rgb.tif')

mask_path = os.path.join(output_dir, 'obvod.shp')
clipped_dem_path = os.path.join(output_dir, 'clipped_dem.tif') # DEM clipped 
stats_path = os.path.join(output_dir, 'stats.gpkg') # Statistika s medianem
normalized_dem_path = os.path.join(output_dir, 'normalized_dem.tif')  # normalized clipped DEM 

filtered_dem_path_rank = os.path.join(output_dir, 'filtered_dem_rank.sdat')  # filtered DEM v puvodnim formatu SAGY pro RANK filter
filtered_dem_gt_path_rank = os.path.join(output_dir, 'filtered_dem_rank.tif') # filtered DEM (GeoTIFF) pro RANK filter

rescaled_dem_path = os.path.join(output_dir, 'rescaled_dem.tif') # DEM rescaled (vypocteny z filterovaneho DEMu)
dem_8bit_path = os.path.join(output_dir, 'dem_8bit.tif') # DEM (8 bit)

filtered_dem_path_hipass = os.path.join(output_dir, 'filtered_dem_hipass.sdat')  # filtered DEM v puvodnim formatu SAGY pro RESAMPLING filter
filtered_dem_gt_path_hipass = os.path.join(output_dir, 'filtered_dem_hipass.tif') # filtered DEM (GeoTIFF) pro RESAMPLING filter
filtered_dem_path_lopass = os.path.join(output_dir, 'filtered_dem_lopass.sdat')  # filtered DEM v puvodnim formatu SAGY (musi byt vystupem RESAMPLING filteru ale nebude dale pouzito)

slope_path = os.path.join(output_dir, 'slope.tif') # Slope vypocteny z filterovaneho DEMu
slope_8bit_path = os.path.join(output_dir, 'slope_8bit.tif') # Slope (8 bit)

tir_r_path = os.path.join(output_dir, 'tir_r.tif') # Red kanal z TIRu

result_path = os.path.join(output_dir, 'result.tif') # Vysledny rastrovy soubor slozeny z 6 bandu => R G B slope DEM tir

# Odstraneni vrstev z projektu
remove_all_layers_from_project()

############################################## 1. Příprava RGB #######################################################
select_bands(ortofoto_path, rgb_path, "ortofoto_RGB", '-b 1 -b 2 -b 3')

############################################## 2. Příprava DEMu ######################################################
# Konverze DXF na SHAPEFILE
# Příkaz pro spuštění ogr2ogr
convert_dxf_to_shapefile(dxf_file_path, mask_path)

# Zobrazeni vrstvy obvodu v QGISu
display_vector_layer(mask_path, "Obvod")

# Zobrazeni vrstvy ortofota v QGISu
display_raster_layer(raster_file_path, "ortofoto")

# Zobrazeni vrstvy DEM v QGISu
display_raster_layer(raster_file_path, "DEM")

# Zobrazeni vrstvy TIR v QGISu
display_raster_layer(raster_file_path, "TIR")

# Nastavení souřadnicového systému (CRS) pro vrstvu
crs = QgsCoordinateReferenceSystem("EPSG:5514") 

# Oříznutí DEMu, aby se počítalo jenom v obvodu daném DXF souborem
clip_raster_by_vector(raster_file_path, mask_path, clipped_dem_path, "Clipped_DEM", crs)

# Výpočet mediánu pro oříznutý DEM
median_value = calculate_median_zonal_statistics(clipped_dem_path, mask_path, stats_path, "Zonal_stats")

# Výpočet normalizovaného DEMu
expression = f'Clipped_DEM@1" - {median_value}'
run_raster_calculator(expression, clipped_dem_path, normalized_dem_path, "Normalized_DEM")

# Filtrace DEMu pomocí RANK filteru (hodí se lépe pro samotný DEM)
run_rank_filter(normalized_dem_path, filtered_dem_path_rank, radius=2)

# Převod filtrovaných DEMů v SAGA formátu na GeoTIFF, aby mohly být zobrazeny v QGISu
convert_SAGA_type_to_GeoTIFF(filtered_dem_path_rank, filtered_dem_gt_path_rank, "Filtered_DEM_rank")

# Rescalování filtrovaného DEM na hodnoty do 0 do 255
rescale_raster_to_0_255(filtered_dem_gt_path_rank, rescaled_dem_path, "Rescaled_DEM")

# Konverze DEMu na 8bit
convert_raster_to_8bit(rescaled_dem_path, dem_8bit_path, "Rescaled_DEM_8bit")

############################################## 3. Příprava SLOPE ######################################################

# Filtrace DEMu na základě RESAMPLING filtru pro účely SLOPE
run_resampling_filter(normalized_dem_path, filtered_dem_path_lopass, filtered_dem_path_hipass, scale=1)

# Převod filtrovaných DEMů v SAGA formátu na GeoTIFF, aby mohly být zobrazeny v QGISu
# Pro slope mne zajímá pouze HIPASS vysledek resampling filteru 
convert_SAGA_type_to_GeoTIFF(filtered_dem_path_hipass, filtered_dem_gt_path_hipass, "Filtered_DEM_hipass")

# Výpočet slope analýzy
run_slope_analysis(filtered_dem_gt_path_hipass, slope_path, "Slope")

# Konverze slope na 8bit
convert_raster_to_8bit(slope_path, slope_8bit_path, "Slope_8bit")

############################################## 4. Příprava TIR ########################################################
select_bands(tir_file_path, tir_r_path, "TIR_R_band", '-b 1')

######################################## 5. Spojení všech 6 bandů #####################################################
input_rasters = [rgb_path,  slope_8bit_path, dem_8bit_path, tir_r_path]
merge_rasters(input_rasters, result_path, "RESULT")

