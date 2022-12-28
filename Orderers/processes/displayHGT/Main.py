import sys, os, json, re, math

from osgeo import gdal, osr, ogr

sys.path.append('/usr/bin/')
import time

import generic

from ast import literal_eval

import warnings
warnings.filterwarnings("ignore")

def Usage():
    print('Usage: trueColour(args)')

def displayHGT(inputDirectory, outputDirectory, display_text = None, productSpecifications = None, aoiwkt = None):

    start = time.time()

    if aoiwkt is not None:
        print("AoI WKT " + aoiwkt)

    hgt_files = findFiles(inputDirectory, 'hgt')
    if len(hgt_files) == 0:
        raise Exception('No HGT files found in input directory')

    hgt_file = hgt_files[0]
    ds = gdal.Open(hgt_file)

    footprint_wkt = generic.getDatasetFootprint(ds)
    cutline_filepath = None
    if aoiwkt is not None:
        gdal.SetConfigOption('GDALWARP_DENSIFY_CUTLINE', 'NO')
        footprint_wkt = generic.calculateCutline(footprint_wkt, aoiwkt)
        print("INTERSECTION: " + footprint_wkt)
        csvFileDirectory = outputDirectory
        cutline_filepath = generic.createCutline(csvFileDirectory, footprint_wkt)

    warpedDs = gdal.Warp('temp', ds, format = 'MEM', cutlineDSName = cutline_filepath,
                  cropToCutline = True, dstSRS = 'EPSG:4326', warpOptions = ['GDALWARP_DENSIFY_CUTLINE=NO'])

    tempFilePath = outputDirectory + '/temp.tiff';
    [scaleParams, exponents] = generic.getScaleParams(warpedDs, 255)
    ds = gdal.Translate(tempFilePath, warpedDs, outputType = gdal.GDT_Byte, scaleParams = scaleParams, exponents = exponents, format = 'GTiff')
    executeOverviews(ds)
    outputFilePath = outputDirectory+ '/productOutput.tiff'
    ds = gdal.Translate(outputFilePath, ds, format = 'GTiff')

    # a bit of clean up
    os.remove(tempFilePath)

    # now write the output json file
    product = {
        "name": "HGT tiff display",
        "productType": "raster",
        "SRS":"EPSG:4326",
        "envelopCoordinatesWKT": footprint_wkt,
        "filePath": outputFilePath,
        "description": "HGT tiff rendering using geocento process on file " + str(hgt_file)
    }
    generic.writeOutput(outputDirectory, True, "HGT tiff rendering using geocento process", [product])

    print("HGT display script finished for DEM file " + str(hgt_file))
    executionTime = time.time() - start
    print(str(executionTime))

def generateWarpFile(outputDirectory, warpedFilePath, aoiwkt, ds, withAlpha = True, srcNoData = None):
    footprintGeometryWKT = generic.getDatasetFootprint(ds)
    if aoiwkt is not None:
        gdal.SetConfigOption('GDALWARP_DENSIFY_CUTLINE', 'NO')
        intersectionWKT = generic.calculateCutline(footprintGeometryWKT, aoiwkt)
        print("FOOTPRINT: " + footprintGeometryWKT)
        print("AOI: " + aoiwkt)
        print("INTERSECTION: " + intersectionWKT)
        
        csvFileDirectory = outputDirectory
        csvFilePath = generic.createCutline(csvFileDirectory, intersectionWKT)
        
        gdal.Warp(warpedFilePath, ds, format = 'VRT', cutlineDSName = csvFilePath,
                  dstAlpha = withAlpha,
                  srcNodata = srcNoData,
                  cropToCutline = True, dstSRS = 'EPSG:4326', warpOptions = ['GDALWARP_DENSIFY_CUTLINE=NO'])

        return intersectionWKT
    else:
        gdal.Warp(warpedFilePath, ds, format = 'VRT',
                  srcNodata = srcNoData,
                  dstAlpha = True,
                  dstSRS = 'EPSG:4326')
        return footprintGeometryWKT

def getFootprintPath(aoiwkt, ds):
    footprintGeometryWKT = generic.getDatasetFootprint(ds)
    if aoiwkt is not None:
        intersectionWKT = generic.calculateCutline(footprintGeometryWKT, aoiwkt)
        return intersectionWKT
    else:
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

def calculateCutline(footprintGeometryWKT, aoiWKT):
    # calculate intersection
    if aoiWKT is None:
        print("No intersection provided!")
        return

    aoiGeometry = ogr.CreateGeometryFromWkt(aoiWKT)
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

    csvFileName = directory + '/cutline.csv'
    csvFile = open(csvFileName, 'w')
    csvFile.write('ID, WKT\n')
    csvFile.write('1, "' + intersectionWKT + '"\n')
    csvFile.close()
    prjFile = open(directory + '/cutline.prj', 'w')
    prjFile.write('EPSG:4326')
    prjFile.close()

    return csvFileName


def executeOverviews(ds):
    # TODO - calculate based on the size of the image
    overviewList = [ 2**j for j in range(1, max(1, int(math.floor(math.log(max(ds.RasterXSize / 256, 1), 2))))) ]
    ds.BuildOverviews("AVERAGE", overviewList)

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
    run_with_args(displayHGT)
