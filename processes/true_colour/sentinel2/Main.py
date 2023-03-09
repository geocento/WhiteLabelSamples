import sys, os, json, re, math

from osgeo import gdal, osr, ogr

sys.path.append('/usr/bin/')
import time

import generic

import warnings
warnings.filterwarnings("ignore")

def Usage():
    print('Usage: trueColour(args)')

def trueColour(inputDirectory, outputDirectory, display_text = None, productSpecifications = None):

    start = time.time()

    print("Product specifications: " + str(productSpecifications))

    # find SAFE directory
    for file in os.listdir(inputDirectory):
        filePath = inputDirectory + file
        print(filePath)
        if os.path.isdir(filePath) and filePath.endswith(".SAFE"):
            safeDirectory = filePath
            break
    if safeDirectory is None:
        sys.exit("Could not find SAFE directory")
    # retrieve the tiff file now
    descriptorPath = os.path.join(safeDirectory, "MTD_MSIL1C.xml")
    print("Opening dataset " + descriptorPath)
    ds = gdal.Open(descriptorPath)

    subdatasets = ds.GetMetadata_List("SUBDATASETS")
    for subdataset in subdatasets:
        if ":TCI:" in subdataset:
            tciFileName = subdataset.split("=")[1]
            break
    if tciFileName is None:
        sys.exit("Could not find true colour image in subdatasets")

    print("TCI file name " + tciFileName)

    tciDs = gdal.Open(tciFileName)

    fileList = tciDs.GetFileList()

    for fileName in fileList:
        if fileName.endswith("_TCI.jp2"):
            jp2FilePath = fileName

    if jp2FilePath is None:
        sys.exit("Could not find jp2 file for true colour image")

    ds = gdal.Open(jp2FilePath)

    warpFilePath = os.path.join(outputDirectory, "warped.vrt")
    productFootprintWKT = generic.generateWarpFile(outputDirectory, warpFilePath, ds)

    ds = gdal.Translate("temp", warpFilePath, outputType = gdal.GDT_Byte, options = ['PHOTOMETRIC=RGB'], format = 'MEM')
    generic.executeOverviews(ds)
    outputFilePath = os.path.join(outputDirectory, 'productOutput.tiff')
    # TODO - check if 16 bits and if 16 bits reduce to 8 bits
    ds = gdal.Translate(outputFilePath, ds, format = 'GTiff')

    # now write the output json file
    product = {
        "name": "True colour image",
        "productType": "raster",
        "SRS":"EPSG:4326",
        "envelopCoordinatesWKT": productFootprintWKT,
        "filePath": outputFilePath,
        "description": "True colour image from Sentinel2 platform",
        "publish": True,
        "publishFilePath": 'productOutput.tiff',
        "publishSLD": "raster"
    }
    generic.writeOutput(outputDirectory, True, "True colour generation using geocento process", [product])

    print("True Colour script finished for SENTINEL2 product(s) at " + inputDirectory)

if __name__ == '__main__':
    generic.run_with_args(trueColour)
