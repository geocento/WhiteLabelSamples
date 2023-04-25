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
        # look for L3 file otherwise L1
        tiff_file = next(value for value in tiff_files if '_L3_' in value)
        if tiff_file is None:
            tiff_file = next(value for value in tiff_files if '_L1_' in value)

    if tiff_file is None:
        raise_error("Could not find suitable tiff file")

    bands = None
    if '_L3_' in tiff_file:
        bands = [1, 2, 3]
    else:
        bands = [3, 2, 1]

    product = output(tiff_file, outputDirectory, bands = bands, scaleMethod = 'cumulative')

    generic.writeOutput(outputDirectory, True, "True colour generation using geocento process", [product])

    print("True Colour script finished for Satellogic product(s) at " + inputDirectory)

def output(imageFilePath, outputDirectory, start = None, bands = [1,2,3], srcNoData = None, scaleMethod = 'cumulative', numBands = 3, outputname='productOutput.tiff'):

    if start is None:
        start = time.time()

    # limit and reorder raster to the selected bands
    imagePath = os.path.join(outputDirectory, "bands.vrt")
    gdal.BuildVRT(imagePath, imageFilePath, bandList = bands)

    ds = gdal.Open(imagePath)

    productFootprintWKT = generic.getDatasetFootprint(ds)
    print("FOOTPRINT: " + productFootprintWKT)

    ds = gdal.Warp(imagePath, ds, format = 'VRT',
                   dstSRS = 'EPSG:4326')

    #Convert to tiff file with 3 bands only.
    print("Translating to tiff file.")
    beforeTranslateTime = time.time() - start
    # check size of image
    fileSize = ds.RasterXSize * ds.RasterYSize
    localOperation = fileSize > 10000 * 10000
    if localOperation:
        print("Local operation")
        tempFile = os.path.join(outputDirectory, "temp.tif")
        ds = gdal.Translate(tempFile, ds, format = "GTiff")
    else:
        ds = gdal.Translate("temp", ds, format = "MEM")
    afterTranslateTime = time.time() - start
    print("Translate execution time: " + str(afterTranslateTime-beforeTranslateTime))

    start = time.time()
    # scale params
    scaleParams = None
    exponents = None
    srcband = ds.GetRasterBand(1)
    needs_scaling = srcband.DataType != 1
    if needs_scaling:
        if scaleMethod == 'cumulative':
            [scaleParams, exponents] = generic.get_cumulative_scale_params(ds, 255, numBands)
        elif scaleMethod == 'minmax':
            [scaleParams, exponents] = generic.getScaleParams(ds, 255, numBands)
        elif scaleMethod == 'identity':
            # just leave as is
            pass
            #[scaleParams, exponents] = [None, None]

    print("Scale params: " + str(scaleParams))
    print("Scale calculation time: " + str(time.time() - start))

    start = time.time()
    if localOperation:
        tempScaledFile = os.path.join(outputDirectory, "tempscaled.tif")
        ds = gdal.Translate(tempScaledFile, ds, scaleParams=scaleParams, exponents=exponents, outputType=gdal.GDT_Byte, creationOptions=["PHOTOMETRIC=RGB", "TILED=YES"], format="GTiff")
    else:
        ds = gdal.Translate("temp", ds, scaleParams=scaleParams, exponents=exponents, outputType=gdal.GDT_Byte, creationOptions=["PHOTOMETRIC=RGB", "TILED=YES"], format="MEM") #, callback=gdal.TermProgress)
    print("Translate execution time: " + str(time.time() - start))

    ds = gdal.Translate("temp", ds, outputType = gdal.GDT_Byte, options = ['PHOTOMETRIC=RGB'], format = 'MEM')
    generic.executeOverviews(ds)
    outputFilePath = os.path.join(outputDirectory, outputname)
    ds = gdal.Translate(outputFilePath, ds, format = 'GTiff')

    # do some cleanup
    ds = None
    if localOperation:
        os.remove(tempFile)
        os.remove(tempScaledFile)

    return {
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


def raise_error(message):
    sys.exit(message)

if __name__ == '__main__':
    generic.run_with_args(trueColour)
