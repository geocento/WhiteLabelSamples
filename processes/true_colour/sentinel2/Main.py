""" the osgeo package contains the GDAL, OGR and OSR libraries """

""" for python 2 and python 3 execution exec(open("./path/to/script.py").read(), globals()) """

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

def trueColour(inputDirectory, outputDirectory, display_text = None, productSpecifications = None):

    start = time.time()

    print("Product specifications: " + str(productSpecifications))

    if True:
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
        productFootprintWKT = generateWarpFile(outputDirectory, warpFilePath, ds)

        ds = gdal.Translate("temp", warpFilePath, outputType = gdal.GDT_Byte, options = ['PHOTOMETRIC=RGB'], format = 'MEM')
        executeOverviews(ds)
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
            "description": "True colour image from Sentinel2 platform"
        }
        generic.writeOutput(outputDirectory, True, "True colour generation using geocento process", [product])

        print("True Colour script finished for SENTINEL2 product(s) at " + inputDirectory)

def generateWarpFile(outputDirectory, warpedFilePath, ds, withAlpha = True, srcNoData = None):
    footprintGeometryWKT = generic.getDatasetFootprint(ds)
    gdal.Warp(warpedFilePath, ds, format = 'VRT',
                  srcNodata = srcNoData,
                  dstAlpha = True,
                  dstSRS = 'EPSG:4326')
    return footprintGeometryWKT

def findFiles(directory, extension):
    print("scanning directory " + directory + " for files with extension " + str(extension))
    foundFiles = []
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            print("file " + name)
            if name.lower().endswith(extension):
                print("Adding file " + name + " at " + dirpath)
                foundFiles.append(os.path.join(dirpath, name))
    return foundFiles

def findFilesRegexp(directory, regexp):
    print("scanning directory " + directory + " for files with regex " + str(regexp))
    foundFiles = []
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            print("file " + name)
            if re.match(regexp, name):
                print("Adding file " + name + " at " + dirpath)
                foundFiles.append(os.path.join(dirpath, name))
    return foundFiles

def findDirectory(directory, substring):
    print("scanning directory " + directory + " for directories with pattern " + str(substring))
    foundFiles = []
    for dirpath, dirnames, files in os.walk(directory):
        for name in dirnames:
            print("directory " + name)
            if substring.lower() in name.lower():
                print("Adding directory " + name + " at " + dirpath)
                foundFiles.append(os.path.join(dirpath, name))
    return foundFiles

def executeWarp(ds, cutlineFilePath):
    return gdal.Warp('temp', ds, format = 'MEM', cutlineDSName = cutlineFilePath, srcNodata = 0, dstAlpha = True, cropToCutline = True, dstSRS = 'EPSG:4326')

def executeOverviews(ds):
    # TODO - calculate based on the size of the image
    overviewList = [ 2**j for j in range(1, max(1, int(math.floor(math.log(max(ds.RasterXSize / 256, 1), 2))))) ]
    ds.BuildOverviews("AVERAGE", overviewList)

def hasRPC(filePath):
    ds = gdal.Open(filePath)
    if ds.GetMetadata('RPC'):
        return True
    else:
        return False

def sanitizeFiles(files):
    sanitizedFiles = []
    for file in files:
        # check if rpc
        if hasRPC(file):
            # try with rpcs
            fileRpc = os.path.join(os.path.dirname(file), os.path.splitext(file)[0] + "_rpc.vrt")
            ds = generic.applyRPCs(file, fileRpc)
            sanitizedFiles.append(fileRpc)
        else:
            # do nothing
            sanitizedFiles.append(file)
    return sanitizedFiles

def getNodata(ds):
    # assumes same value for all bands
    return ds.GetRasterBand(1).GetNoDataValue()

def panSharpen(outputDirectory, panFiles, bandFiles, bands = None, noData = None):

    # create VRT with the files
    if len(panFiles) == 1:
        panFilePath = panFiles[0]
    elif len(panFiles) > 1:
        # mosaic the tif files
        panFilePath = outputDirectory + '/panfiles.vrt'
        gdal.BuildVRT(panFilePath, panFiles)
    else:
        sys.exit('No pan files')

    if len(bandFiles) == 1:
        bandsFilePath = bandFiles[0]
    elif len(bandFiles) == 3:
        # assumes bands are in the right order
        bandsFilePath = outputDirectory + '/spectral.vrt'
        gdal.BuildVRT(bandsFilePath, bandFiles, separate = True)
    else:
        sys.exit('No pan files')

    panSharpenFilePath = outputDirectory + '/pansharpen.vrt';

    parameters = ['', panFilePath, bandsFilePath, panSharpenFilePath,
                  #'-co', 'PHOTOMETRIC=RGB',
                  '-of', 'VRT']
    if noData is not None:
        parameters.append('-nodata')
        parameters.append(noData)

    if bands is not None:
        addBandParameters(parameters, bands)

    print("Pan sharpening parameters " + str(parameters))
    gdal_pansharpen.gdal_pansharpen(parameters)

    if not os.path.exists(panSharpenFilePath):
        sys.exit("Pansharpen failed, no file at " + panSharpenFilePath)

    return panSharpenFilePath

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

def run_with_args(func, args=None):
    """Parse arguments from ``sys.argv`` or given list of *args* and pass
    them to *func*.
    If ``--help`` is passed to program, print usage information.
    """
    args, kwargs = parse_args(args)
    if kwargs.get('help'):
        from inspect import getargspec
        argspec = getargspec(func)
        if argspec.defaults:
            defaults_count = len(argspec.defaults)
            args = argspec.args[:-defaults_count]
            defaults = zip(argspec.args[-defaults_count:], argspec.defaults)
        else:
            args = argspec.args
            defaults = []
        usage = 'usage: %s [--help]' % sys.argv[0]
        if args:
            usage += ' ' + ' '.join(args)
        if defaults:
            usage += ' ' + ' '.join(('[%s=%r]' % pair for pair in defaults))
        if argspec.varargs:
            usage += ' ' + '*' + argspec.varargs
        if argspec.keywords:
            usage += ' ' + '**' + argspec.keywords
        print(usage)
    else:
        return func(*args, **kwargs)


def parse_args(args=None):
    """Parse positional and keyword arguments from ``sys.argv`` or given list
    of *args*.
    :param args: list of string to parse, defaults to ``sys.argv[1:]``.
    :return: :class:`tuple` of positional args and :class:`dict` of keyword
        arguments.
    Positional arguments have no specific syntax. Keyword arguments must be
    written as ``--{keyword-name}={value}``::
        >>> parse_args(['1', 'hello', 'True', '3.1415926', '--force=True'])
        ((1, 'hello', True, 3.1415926), {'force': True})
    """
    if args is None:
        args = sys.argv[1:]

    positional_args, kwargs = (), {}
    for arg in args:
        if arg.startswith('--'):
            arg = arg[2:]
            try:
                key, raw_value = arg.split('=', 1)
                value = parse_literal(raw_value)
            except ValueError:
                key = arg
                value = True
            kwargs[key.replace('-', '_')] = value
        else:
            positional_args += (parse_literal(arg),)

    return positional_args, kwargs


def parse_literal(string):
    """Parse Python literal or return *string* in case :func:`ast.literal_eval`
    fails."""
    try:
        return literal_eval(string)
    except (ValueError, SyntaxError):
        return string

if __name__ == '__main__':
    run_with_args(trueColour)
