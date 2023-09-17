import sys, os, json, re, math

from osgeo import gdal, osr, ogr

sys.path.append('/usr/bin/')
import gdal_pansharpen
import time

import generic

from xml.dom import minidom

import warnings
warnings.filterwarnings("ignore")

from ast import literal_eval

def Usage():
    print('Usage: trueColour(args)')

def trueColour(inputDirectory, outputDirectory, productSpecifications = None):

    start = time.time()

    print("Product specifications: " + str(productSpecifications))

    driver = gdal.GetDriverByName('DIMAP')
    driver.Register()

    # check if bundle or pansharpened
    # look for DIMAP files
    dimapFiles = generic.findFilesRegexp(inputDirectory, '(^DIM_PHR1).+(.XML$)')
    imagePath = None
    dimapBandFile = None
    if len(dimapFiles) == 0:
        sys.exit("Missing dimap files in directory " + inputDirectory)

    if len(dimapFiles) == 1:
        imagePath = dimapFiles[0]
        dimapBandFile = dimapFiles[0]
    elif len(dimapFiles) == 2:
        msFilePath = panFilePath = None
        if re.match('(^DIM_PHR1).+(_P_).+(.XML$)', os.path.basename(dimapFiles[0])):
            panFilePath = dimapFiles[0]
            msFilePath = dimapFiles[1]
        else:
            panFilePath = dimapFiles[1]
            msFilePath = dimapFiles[0]
        print("Pan file " + panFilePath + " and MS file " + msFilePath)
        dimapBandFile = msFilePath

        # check if rpc
        if generic.hasRPC(panFilePath):
            # try with rpcs
            msFilePathRpc = os.path.join(outputDirectory, "msfile_rpc.vrt")
            ds = generic.applyRPCs(msFilePath, msFilePathRpc)
            msFilePath = msFilePathRpc
            # try with rpcs
            panFilePathRpc = os.path.join(outputDirectory, "panfile_rpc.vrt")
            ds = generic.applyRPCs(panFilePath, panFilePathRpc)
            panFilePath = panFilePathRpc

        imagePath = os.path.join(outputDirectory, "pansharpen.vrt")

        # check if jp2 files
        jp2Files = generic.findFilesRegexp(inputDirectory, '.+(.JP2$)')
        isJPEG200 = len(jp2Files) > 0

        if isJPEG200:
            # convert the jp2 files to tiff files as there is a bug with the driver
            panFileTiff = os.path.join(outputDirectory, "panFile.tiff")
            gdal.Translate(panFileTiff, panFilePath)
            msFileTiff = os.path.join(outputDirectory, "msFile.tiff")
            gdal.Translate(msFileTiff, msFilePath)
            gdal_pansharpen.gdal_pansharpen(['', panFileTiff, msFileTiff, imagePath, '-b', '1', '-b', '2', '-b', '3', '-nodata', '0', '-co', 'PHOTOMETRIC=RGB', '-of', 'VRT'])
        else:
            gdal_pansharpen.gdal_pansharpen(['', panFilePath, msFilePath, imagePath, '-b', '1', '-b', '2', '-b', '3', '-nodata', '0', '-co', 'PHOTOMETRIC=RGB', '-of', 'VRT'])
    else:
        sys.exit("Missing image files in directory " + inputDirectory)

    # collect band information
    bandOrder = [1,2,3]
    try:
        xmldoc = minidom.parse(dimapBandFile)
        bands_list = xmldoc.getElementsByTagName("Raster_Index")
        nodes = xmldoc.getElementsByTagName("Band_Display_Order")
        if bands_list and nodes:
            band_indexes = {}
            for band in bands_list:
                band_id = band.getElementsByTagName("BAND_ID")[0].firstChild.data
                band_index = band.getElementsByTagName("BAND_INDEX")[0].firstChild.data
                band_indexes[band_id] = band_index

            bandOrder = [
                int(band_indexes[nodes[0].getElementsByTagName("RED_CHANNEL")[0].firstChild.data]),
                int(band_indexes[nodes[0].getElementsByTagName("GREEN_CHANNEL")[0].firstChild.data]),
                int(band_indexes[nodes[0].getElementsByTagName("BLUE_CHANNEL")[0].firstChild.data])
            ]
            print('Computed band order from DIMAP is ' + str(bandOrder))
    except:
        print('Could not compute band order using default one instead')

    # find the scaling method required
    scaleMethod = 'cumulative'
    # if we have radiometric processing level of display then no need for scaling
    radiometric = xmldoc.getElementsByTagName("RADIOMETRIC_PROCESSING")
    if radiometric and len(radiometric) > 0:
        radiometric_level = radiometric[0].firstChild.data
        if radiometric_level == 'DISPLAY':
            print('Radiometric level is DISPLAY no scale method applied')
            scaleMethod = 'identity'
        else:
            print('Radiometric level is ' + str(radiometric_level))
    else:
        print('No radiometric level specified')

    # TODO - use the value from the XML file instead
    srcNoData = 0
    product = output(imagePath, outputDirectory, start, bands = bandOrder, srcNoData=srcNoData, scaleMethod = scaleMethod)

    generic.writeOutput(outputDirectory, True, "True colour generation using geocento process", [product])
    print("True Colour script finished for PLEIADES product(s) at " + inputDirectory)

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
        "description": "True colour image from Maxar platform",
        "publish": True,
        "publishFilePath": outputname,
        "publishSLD": "raster"
    }


if __name__ == '__main__':
    generic.run_with_args(trueColour)
