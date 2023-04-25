import sys, os, json, re, numpy as np, math

import osgeo
from osgeo import gdal, osr, ogr

import warnings
warnings.filterwarnings("ignore")

from ast import literal_eval

sys.path.append('/usr/bin/')
import gdal_pansharpen

print(str(np.__path__))

srs_4326 = osr.SpatialReference()
srs_4326.ImportFromEPSG(4326)
if int(osgeo.__version__[0]) >= 3:
    # GDAL 3 changes axis order: https://github.com/OSGeo/gdal/issues/1546
    srs_4326.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

def calculateCutline(footprintGeometryWKT, aoiWKT):
    # calculate intersection
    if aoiWKT is None:
        print("No intersection provided!")
        return

    aoiGeometry = ogr.CreateGeometryFromWkt(aoiWKT, srs_4326)
    footprintGeometry = ogr.CreateGeometryFromWkt(footprintGeometryWKT)

    intersectionGeometry = footprintGeometry.Intersection(aoiGeometry)
    if intersectionGeometry is None:
        return

    return intersectionGeometry.ExportToWkt()

def createCutline(directory, footprintGeometryWKT, aoiWKT):
    createCutline(directory, calculateCutline(footprintGeometryWKT, aoiWKT))

def createCutline(directory, intersectionWKT):
    if intersectionWKT is None:
        return

    csvFileName = os.path.join(directory, 'cutline.csv')
    csvFile = open(csvFileName, 'w')
    csvFile.write('ID, WKT\n')
    csvFile.write('1, "' + intersectionWKT + '"\n')
    csvFile.close()
    prjFile = open(os.path.join(directory, 'cutline.prj'), 'w')
    prjFile.write('EPSG:4326')
    prjFile.close()

    return csvFileName

def executeOverviews(ds):
    # TODO - calculate based on the size of the image
    overviewList = [2, 4, 8, 16, 32]
    ds.BuildOverviews( "CUBIC", overviewList)

def writeOutput(directory, success, message, products):
    outputValues = {
        "success": success,
        "message": message,
        "products": products
    }
    with open(os.path.join(directory, 'output.json'), 'w') as outfile:
        json.dump(outputValues, outfile)

def getDatasetFootprint(datafile):

    if datafile is None:
        print('Missing dataset')
        return None

    cols = datafile.RasterXSize
    rows = datafile.RasterYSize
    bands = datafile.RasterCount

    """Print the information to the screen. Converting the numbers returned to strings using str()"""

    print("Number of columns: " + str(cols))
    print("Number of rows: " + str(rows))
    print("Number of bands: " + str(bands))

    """First we call the GetGeoTransform method of our datafile object"""
    geoinformation = datafile.GetGeoTransform()

    """The top left X and Y coordinates are at list positions 0 and 3 respectively"""

    topLeftX = geoinformation[0]
    topLeftY = geoinformation[3]

    """Print this information to screen"""

    print("Top left X: " + str(topLeftX))
    print("Top left Y: " + str(topLeftY))

    """first we access the projection information within our datafile using the GetProjection() method. This returns a string in WKT format"""

    projInfo = datafile.GetProjection()

    """Then we use the osr module that comes with GDAL to create a spatial reference object"""

    spatialRef = osr.SpatialReference()

    """We import our WKT string into spatialRef"""

    spatialRef.ImportFromWkt(projInfo)

    """We use the ExportToProj4() method to return a proj4 style spatial reference string."""

    spatialRefProj = spatialRef.ExportToProj4()

    """We can then print them out"""

    print("WKT format: " + str(spatialRef))
    print("Proj4 format: " + str(spatialRefProj))

    gcps = datafile.GetGCPs()

    projection = None
    if gcps is None or len(gcps) == 0:
        print('No GCPs found in file')
        geotransform = datafile.GetGeoTransform()
        projection = datafile.GetProjection()
    else:
        geotransform = gdal.GCPsToGeoTransform( gcps )
        projection = datafile.GetGCPProjection()

    if geotransform is None:
        print('Unable to extract a geotransform.')
        return None

    def toWKT(col, row):
        lng = geotransform[0] + col * geotransform[1] + row * geotransform[2]
        lat = geotransform[3] + col * geotransform[4] + row * geotransform[5]
        return str(lng) + " " + str(lat)

    wktGeometry = "POLYGON((" + toWKT(0, 0)  + ", " + toWKT(0, rows) + ", " + toWKT(cols, rows) + ", " + toWKT(cols, 0) + ", " + toWKT(0, 0) + "))"
    print("Footprint geometry " + wktGeometry + ", projection is " + projection)

    footprint = ogr.CreateGeometryFromWkt(wktGeometry, srs_4326)

    # now make sure we have the footprint in 4326
    if projection is not None:
        source = osr.SpatialReference(projection)
        source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source, srs_4326)
        footprint.Transform(transform)
        print("Footprint geometry reprojected " + footprint.ExportToWkt())

    return footprint.ExportToWkt()
    
# apply rpcs and return VRT file
def applyRPCs(inputFilePath, outputFilePath):
    ds = gdal.Warp(outputFilePath, inputFilePath, format = 'VRT', rpc = True)
    return ds

def getScaleParams(datafile, maxScale = None, numBands = 3):

    if datafile is None:
        print('No dataset provided')
        return None

    # check number of bands
    # if RGB bands are supposed to be ordered as RGB already
    bandList = range(1, numBands + 1)
    print(str(bandList))

    minBands = sys.maxsize
    maxBands = -1 * minBands
    scaleParams = []
    exponents = []
    for band in bandList:

        print("[ GETTING BAND ]: ", band)
        srcband = datafile.GetRasterBand(band)
        if srcband is None:
            continue

        stats = srcband.GetStatistics( True, True )
        if stats is None:
            continue

        minValue = stats[0]
        maxValue = stats[1]
        mean = stats[2]
        stddev = stats[3]
        if(minValue > 0 and minValue < minBands):
            minBands = minValue
        if(maxValue > maxBands):
            maxBands = maxValue

        # calculate the min max to stretch to
        dataType = srcband.DataType
        if maxScale is None:
            if dataType == 1:
                maxScale = 255
            elif dataType == 2:
                maxScale = 65535
            else:
                maxScale = 255
                
        # do scaling on a band basis
        scaleParams.append([minValue, maxValue, 1, maxScale])
        exponents.append(0.5)

        print("[ STATS ] =  Minimum=%.3f, Maximum=%.3f, Mean=%.3f, StdDev=%.3f" % ( \
            stats[0], stats[1], stats[2], stats[3] ))


    print("Min bands is " + str(minBands) + " and max bands is " + str(maxBands))

    print("Scale value is " + str(scaleParams))

    return [scaleParams, exponents];
    
def getSimpleScaleParams(datafile, maxScale = None, numBands = 3):

    # TODO - use computeBandStats instead

    if datafile is None:
        print('No dataset provided')
        return None

    # check number of bands
    # if RGB bands are supposed to be ordered as RGB already
    bandList = range(1, numBands + 1)
    print(str(bandList))

    minBands = sys.maxsize
    maxBands = -1 * minBands
    scaleParams = []
    exponents = []
    for band in bandList:

        print("[ GETTING BAND ]: ", band)
        srcband = datafile.GetRasterBand(band)
        if srcband is None:
            continue

        print("No data value is " + str(srcband.GetNoDataValue()))
        stats = srcband.GetStatistics( True, True )
        if stats is None:
            continue

        minValue = stats[0]
        maxValue = stats[1]
        if(minValue < minBands):
            minBands = minValue
        if(maxValue > maxBands):
            maxBands = maxValue

        print("[ STATS ] =  Minimum=%.3f, Maximum=%.3f, Mean=%.3f, StdDev=%.3f" % ( \
            stats[0], stats[1], stats[2], stats[3] ))
            
    for band in bandList:

        srcband = datafile.GetRasterBand(band)
        if srcband is None:
            continue

        # calculate the min max to stretch to
        dataType = srcband.DataType
        if maxScale is None:
            if dataType == 1:
                maxScale = 255
            elif dataType == 2:
                maxScale = 65535
            else:
                maxScale = 255
        
        # do scaling on a band basis
        scaleParams.append([minBands, maxBands, 0, maxScale])

        exponents.append(0.5)

    return [scaleParams, exponents];


def get_cumulative_scale_params(datafile, max_scale = None, num_bands = None):

    if datafile is None:
        print('No dataset provided')
        return None

    # check number of bands
    if num_bands is None:
        num_bands = datafile.RasterCount

    band_list = range(1, num_bands + 1)
    print('Band list to process ', band_list)

    threshold = 1e8
    scaleParams = []
    exponents = []
    for band in band_list:

        print("[ GETTING BAND ]: ", band)
        srcband = datafile.GetRasterBand(band)
        if srcband is None:
            continue

        # check if we have a no data value
        noData = srcband.GetNoDataValue()

        values = srcband.ReadAsArray()
        if noData is not None:
            values = values[values != noData]

        min_max = np.nanpercentile(values, [2, 98])

        # do scaling on a band basis
        scaleParams.append([min_max[0], min_max[1], 1, max_scale])
        exponents.append(0.5)

    print("Scale value is " + str(scaleParams))

    return [scaleParams, None];

def generateWarpFile(outputDirectory, warpedFilePath, ds, withAlpha = True, srcNoData = None):
    footprintGeometryWKT = getDatasetFootprint(ds)
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
            ds = applyRPCs(file, fileRpc)
            sanitizedFiles.append(fileRpc)
        else:
            # do nothing
            sanitizedFiles.append(file)
    return sanitizedFiles

def getNodata(ds):
    # assumes same value for all bands
    return ds.GetRasterBand(1).GetNoDataValue()

def panSharpen(outputDirectory, panFiles, bandFiles, bands=None, noData=None, basename=''):

    # create VRT with the files
    if len(panFiles) == 1:
        panFilePath = panFiles[0]
    elif len(panFiles) > 1:
        # mosaic the tif files
        panFilePath = os.path.join(outputDirectory, basename + 'panfiles.vrt')
        gdal.BuildVRT(panFilePath, panFiles)
    else:
        sys.exit('No pan files')

    if len(bandFiles) == 1:
        bandsFilePath = bandFiles[0]
    elif len(bandFiles) == 3:
        # assumes bands are in the right order
        bandsFilePath = os.path.join(outputDirectory, basename + 'spectral.vrt')
        gdal.BuildVRT(bandsFilePath, bandFiles, separate = True)
    else:
        sys.exit('No pan files')

    panSharpenFilePath = os.path.join(outputDirectory, basename + 'pansharpen.vrt')

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
