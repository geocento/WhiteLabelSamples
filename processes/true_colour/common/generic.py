import sys, os, json, numpy as np, math

from osgeo import gdal, osr, ogr

import warnings
warnings.filterwarnings("ignore")

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
    overviewList = [2, 4, 8, 16, 32]
    ds.BuildOverviews( "CUBIC", overviewList)

def writeOutput(directory, success, message, products):
    outputValues = {
        "success": success,
        "message": message,
        "products": products
    }
    with open(directory + '/output.json', 'w') as outfile:
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

    footprint = ogr.CreateGeometryFromWkt(wktGeometry)

    # now make sure we have the footprint in 4326
    if projection is not None:
        source = osr.SpatialReference(projection)
        target = osr.SpatialReference()
        target.ImportFromEPSG(4326)
        transform = osr.CoordinateTransformation(source, target)
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

def getCumulativeCountScaleParams(datafile, maxScale = None, numBands = 3):

    if datafile is None:
        print('No dataset provided')
        return None

    # check number of bands
    # if RGB bands are supposed to be ordered as RGB already
    bandList = range(1, numBands + 1)
    print(str(bandList))

    threshold = 1e8
    scaleParams = []
    exponents = []
    for band in bandList:

        print("[ GETTING BAND ]: ", band)
        srcband = datafile.GetRasterBand(band)
        if srcband is None:
            continue
        
        # check if we have a no data value
        noData = srcband.GetNoDataValue()

        # check size and divide in smaller chunks if needed
        width = srcband.XSize
        height = srcband.YSize
        imageSize = width * height
        chunks = int(math.ceil(imageSize / threshold))
        chunkHeight = float(height) / chunks
        
        # calculate the min max to stretch to
        dataType = srcband.DataType
        if dataType == 1:
            minBin = 0
            maxBin = 255
        elif dataType == 2:
            minBin = 0
            maxBin = 65535
        elif dataType == 3:
            minBin = -32768
            maxBin = 32767
        else:
            print("Unknown data type provided for this band, value is " + str(dataType) + ", exiting")
            sys.exit(-1)

        # if no max scale is provided calculate the min max to stretch to
        if maxScale is None:
            print('No max scale provided, using default value')
            if dataType == 1:
                maxScale = 255
            elif dataType == 2 or dataType == 3:
                maxScale = 65535
            else:
                maxScale = 255

        cumulatedHistSize = 0
        histogram = None
        # do calculations over chunks
        print("Calculate value over chunks with width ", width, " height ", height, " chunks ", chunks, " chunkHeight ", chunkHeight)
        for chunk in range(0, chunks):
            startHeight = int(math.floor(chunk * chunkHeight))
            stopHeight = int(min(math.floor((chunk + 1) * chunkHeight), height) - startHeight)
            print("Get min max values for image values between ", startHeight, " and ", (startHeight + stopHeight))
            arr = srcband.ReadAsArray(0, startHeight, width, stopHeight)
            if noData is not None:
                arr = arr[arr != noData]
            cumulatedHistSize += arr.size
            print("Band size ", arr.size, " standard deviation ", np.std(arr), " and mean ", np.mean(arr))
            hist, bin_edges = np.histogram(arr, bins = maxBin - minBin, range = [minBin, maxBin])
            if histogram is None:
                histogram = hist
            else:
                histogram = histogram + hist

        print("Cumulated histogram size ", cumulatedHistSize, " standard deviation ", np.std(histogram), " and mean ", np.mean(histogram))

        # now work out min and max
        minValue = None
        maxValue = None
        sumValues = 0
        for value in range(0, len(histogram)):
            sumValues = sumValues + histogram[value]
            if minValue is None and sumValues > cumulatedHistSize * 0.02:
                minValue = range(minBin, maxBin)[value]
            if maxValue is None and sumValues > cumulatedHistSize * 0.98:
                maxValue = range(minBin, maxBin)[value]
                break

        # do scaling on a band basis
        scaleParams.append([minValue, maxValue, 1, maxScale])
        exponents.append(0.5)

    print("Scale value is " + str(scaleParams))

    return [scaleParams, None];
    
