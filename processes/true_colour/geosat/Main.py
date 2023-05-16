import sys, os, json, re, math

import numpy as np
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


def trueColour(inputDirectory, outputDirectory, productSpecifications = None):

    # get the TIL files
    tiff_files = generic.findFiles(inputDirectory, ('tiff', 'tif'))
    # exclude browse
    tiff_files = list(filter(lambda filename: '_browser.' not in filename, tiff_files))

    num_til_files = len(tiff_files)

    if num_til_files == 0:
        raise_error("Missing TIFF file in directory")

    # we could have one single pan-sharpened file or a pair of bundle files or 2-3 PS or bundle stereo files
    # look for PAN in directory to find out if bundle and group them if they are
    pan_tif_files = []
    mul_tif_files = []
    ps_tif_files = []
    for tiff_file in tiff_files:
        filename = os.path.basename(tiff_file)
        if '_PSH1_' in filename:
            ps_tif_files.append(tiff_file)
        elif '_MS1_' in filename or '_MS_' in filename:
            mul_tif_files.append(tiff_file)
        elif '_PAN1_' in filename or '_PAN_' in filename:
            pan_tif_files.append(tiff_file)
        else:
            ps_tif_files.append(tiff_file)

    # deal with bundle first
    if len(pan_tif_files) > 0:
        for pan_tif_file in pan_tif_files:
            # look for matching mul file
            if '_PAN1_' in filename:
                mul_tif_file_name = os.path.basename(pan_tif_file).replace('_PAN1_', '_MS1_')
            else:
                mul_tif_file_name = os.path.basename(pan_tif_file).replace('_PAN_', '_MS_')
            mul_tif_files = list(filter(lambda file: os.path.basename(file) == mul_tif_file_name, mul_tif_files))
            if len(mul_tif_files) == 0:
                raise_error(f'Missing MUL file for PAN file {pan_tif_file}')
            mul_tif_file = mul_tif_files[0]
            # check if rpc
            if generic.hasRPC(pan_tif_file):
                mul_tif_file_rpc = os.path.splitext(os.path.basename(mul_tif_file))[0] + "_rpc.vrt"
                ds = generic.applyRPCs(mul_tif_file, mul_tif_file_rpc)
                mul_tif_file = mul_tif_file_rpc
                pan_tif_file_rpc = os.path.splitext(os.path.basename(pan_tif_file))[0] + "_rpc.vrt"
                ds = generic.applyRPCs(pan_tif_file, pan_tif_file_rpc)
                pan_tif_file = pan_tif_file_rpc
            # generate pan-sharpened file
            ps_til_file = generic.panSharpen(outputDirectory, [pan_tif_file], [mul_tif_file], basename=os.path.splitext(os.path.basename(pan_tif_file))[0] + "_")
            ps_tif_files.append(ps_til_file)

    # now generate the products
    products = []
    for ps_til_file in ps_tif_files:
        ds = gdal.Open(ps_til_file)
        numBands = ds.RasterCount
        print(f"Number of bands is {numBands}")

        outputname = f'productOutput_{len(products) + 1}.tiff'
        if numBands == 3:
            bands = [1, 2, 3]
        elif numBands == 4:
            bands = [3, 2, 1]
        else:
            raise_error("Number of bands not supported: ", numBands)

        product = output(ps_til_file, outputDirectory, bands = bands, scaleMethod = 'cumulative', outputname=outputname, srcNoData=0)

        products.append(product)

    generic.writeOutput(outputDirectory, True, "True colour generation using geocento process", products)
    print("True Colour script finished for Geosat product(s) at " + inputDirectory)


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
            [scaleParams, exponents] = generic.get_cumulative_scale_params(ds, 255, numBands, srcNoData=srcNoData)
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

    # make sure we remove the no data value
    for i in range(ds.RasterCount):
        ds.GetRasterBand(i+1).DeleteNoDataValue()

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
        "description": "True colour image from Maxar platform",
        "publish": True,
        "publishFilePath": outputname,
        "publishSLD": "raster"
    }

def raise_error(message):
    sys.exit(message)


if __name__ == '__main__':
    generic.run_with_args(trueColour)
