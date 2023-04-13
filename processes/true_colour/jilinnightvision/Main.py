import sys, os, json, re, math

from osgeo import gdal, osr, ogr

sys.path.append('/usr/bin/')
import time

# add to import common directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))
import generic

import warnings
warnings.filterwarnings("ignore")

def Usage():
    print('Usage: trueColour(args)')

def trueColour(inputDirectory, outputDirectory, display_text = None, productSpecifications = None):

    start = time.time()

    print("Product specifications: " + str(productSpecifications))

    tiff_file = None
    # find TIFF files
    tiff_files = generic.findFiles(inputDirectory, 'tif')
    if len(tiff_files) == 0: sys.exit('No tiff files provided')
    if len(tiff_files) == 1: tiff_file = tiff_files[0]
    else:
        # look for file with a Byte range
        for file in tiff_files:
            ds = gdal.Open(file)
            if ds.GetRasterBand(1).DataType == 1:
                tiff_file = file
                break

    if tiff_file is None:
        sys.exit("Could not find suitable tiff file")

    ds = gdal.Open(tiff_file)

    has_rpc = len(generic.findFilesRegexp(inputDirectory, '(.*)_rpc.txt')) > 0
    warpFilePath = os.path.join(outputDirectory, "warped.vrt")
    ds = gdal.Warp(warpFilePath, ds, format = 'VRT',
              srcNodata = None,
              dstAlpha = True,
              rpc = has_rpc,
              dstSRS = 'EPSG:4326')
    productFootprintWKT = generic.getDatasetFootprint(ds)

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
        "description": "True colour image from JILIN Nightvision platform",
        "publish": True,
        "publishFilePath": 'productOutput.tiff',
        "publishSLD": "raster"
    }
    generic.writeOutput(outputDirectory, True, "True colour generation using geocento process", [product])

    print("True Colour script finished for JILIN Nightvision product(s) at " + inputDirectory)

if __name__ == '__main__':
    generic.run_with_args(trueColour)
