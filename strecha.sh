#!/bin/bash

QGIS_PYTHON="/usr/bin/python3"
QGIS_SCRIPT="/home/linduska/strecha/strecha.py"

# Parametry
PARAMS=(
   'DEM_PATH=/home/linduska/strecha/strecha1/dem.tif DXF_PATH=/home/linduska/strecha/strecha1/obvod.dxf OUTPUT_DIR=/home/linduska/strecha/strecha1/output'
)

# Spusteni skriptu pro ruzne nastaveni parametru
for params in "${PARAMS[@]}"
do
  $QGIS_PYTHON $QGIS_SCRIPT $params
done