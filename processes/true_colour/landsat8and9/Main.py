import sys, os, json, re, math

from osgeo import gdal, osr, ogr

# add for gdal scripts support
sys.path.append('/usr/bin/')
# add to import common directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))
import generic
import gdal_pansharpen

import warnings
warnings.filterwarnings("ignore")

def Usage():
    print('Usage: trueColour(args)')

def trueColour(input_directory, output_directory, productSpecifications = None):

    print("Product specifications: " + str(productSpecifications))

    band_files = []
    # get the required bands
    for file in os.listdir(input_directory):
        file_path = os.path.join(input_directory, file)
        if file_path.upper().endswith("_B2.TIF") or \
                file_path.upper().endswith("_B3.TIF") or \
                file_path.upper().endswith("_B4.TIF"):
            band_files.append(file_path)
        elif file_path.upper().endswith("_B8.TIF"):
            band8_file_path = file_path

    if len(band_files) != 3 or band8_file_path is None:
        sys.exit("Missing bands in Landsat directory")

    # make sure the bands are arranged in the right order
    band_files = sorted(band_files, reverse = True)

    # create vrt for bands
    bands_file_path = os.path.join(output_directory, 'spectral.vrt')
    gdal.BuildVRT(bands_file_path, band_files, separate = True)

    pan_sharpen_file_path = os.path.join(output_directory, 'pansharpen.vrt');

    gdal_pansharpen.gdal_pansharpen(['', band8_file_path, bands_file_path, pan_sharpen_file_path, '-nodata', '0', '-co', 'PHOTOMETRIC=RGB', '-of', 'VRT'])

    # stretch the values
    ds = gdal.Open(pan_sharpen_file_path)

    warped_file_path = os.path.join(output_directory, 'warped.vrt')
    product_footprint_wkt = generic.generateWarpFile(output_directory, warped_file_path, ds)

    [scaleParams, exponents] = generic.getScaleParams(ds, 255)
    print(str(scaleParams))

    print('Translating to tiff file')

    ps = gdal.Translate("temp", warped_file_path, scaleParams = scaleParams, exponents = exponents, outputType = gdal.GDT_Byte, options = ['PHOTOMETRIC=RGB'], format = 'MEM')

    print('Generate overviews')
    generic.executeOverviews(ps)

    print('Save with overviews')
    output_file_path = os.path.join(output_directory, 'productOutput.tiff')
    gdal.Translate(output_file_path, ps, format = 'GTiff')

    # now write the output json file
    product = {
        "name": "True colour image",
        "productType": "raster",
        "SRS":"EPSG:4326",
        "envelopCoordinatesWKT": product_footprint_wkt,
        "filePath": output_file_path,
        "description": "True colour image from Landsat 8 platform",
        "publish": True,
        "publishFilePath": 'productOutput.tiff',
        "publishSLD": "raster"
    }
    generic.writeOutput(output_directory, True, "True colour generation using geocento process", [product])

    print("True Colour script finished for LANDSAT8 and 9 STANDARD product(s) at " + input_directory)

def getNodata(ds):
    # assumes same value for all bands
    return ds.GetRasterBand(1).GetNoDataValue()

def addBandParameters(parameters, bands):
    for band in bands:
        parameters.append('-b')
        parameters.append(str(band))

def fileType(filesPathArray, string, string2, outputArray, expectedLength):
    returnStatus = True
    for filePath in filesPathArray:
        path, fileName = os.path.split(filePath)
        if string and string2:
            if string in fileName.upper():
                outputArray.append(filePath)
            elif string2 in fileName.upper():
                outputArray.append(filePath)
        elif string:
            if string in fileName.upper():
                outputArray.append(filePath)
        else:
            print("Missing string.")
    # Check the correct number of files have been added to the array.
    if len(outputArray) < expectedLength:
        returnStatus = False
        if string and string2:
            print("Unable to locate file with " + string + " or " + string2 + " in filename.")
        elif string:
            print("Unable to locate file with " + string + " in filename.")
    elif len(outputArray) > expectedLength:
        returnStatus = False
        if string and string2:
            print("More than one file with " + string + " or " + string2 + " in filename.")
        elif string:
            print("More than one file with " + string + " in filename.")
    return returnStatus

def mosaic(filePathsArray, fileName, outputDirectory):
    filePath = os.path.join(outputDirectory, fileName)
    if len(filePathsArray) > 1: #If there is more than one pan file, mosaic the tiles.
        gdal.BuildVRT(filePath, filePathsArray)
        print("Mosaic complete.")
    elif len(filePathsArray) == 1:
        #Convert to vrt format.
        gdal.Translate(filePath, filePathsArray[0], format = "VRT")
        print("No mosaic necessary.")
    else:
        filePath = False
    return filePath

def convertBandNumber(value):
    if value == 'B2':
        return 1
    elif value == 'B1':
        return 2
    elif value == 'B0':
        return 3
    else:
        return None
    #return int(value.lower().replace('b', '')) + 1

if __name__ == '__main__':
    generic.run_with_args(trueColour)
