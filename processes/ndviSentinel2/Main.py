""" the osgeo package contains the GDAL, OGR and OSR libraries """

""" for python 2 and python 3 execution exec(open("./path/to/script.py").read(), globals()) """

import sys, os, json

from osgeo import gdal, ogr

import numpy as np
from numpy import *

import generic

PYTHONUNBUFFERED=1

def Usage():
    print('Usage: trueColour(args)')

def ndviRaster(argv):

    np.seterr(divide='ignore', invalid='ignore')

    # TODO - use gdal.GeneralCmdLineProcessor( argv ) instead
    inputdirectory = sys.argv[1]
    outputdirectory = sys.argv[2]
    producttype = ''
    aoiwkt = None

    print('Input args ' + str(argv))

    safeDirectory = None
    # find SAFE directory
    for file in os.listdir(inputdirectory):
        filePath = os.path.join(inputdirectory, file)
        print('File path is ' + str(filePath))
        if os.path.isdir(filePath) and filePath.endswith(".SAFE"):
            safeDirectory = filePath
            break
    if safeDirectory is None:
        sys.exit("Could not find SAFE directory")
    # retrieve the tiff file now
    descriptorPath = safeDirectory + "/MTD_MSIL1C.xml"
    print("Opening dataset " + descriptorPath)
    ds = gdal.Open(descriptorPath)

    b4FileName = None
    b8aFileName = None
    jp2Files = findFiles(safeDirectory, 'jp2')
    for jp2File in jp2Files:
        print('File name: ' + jp2File)
        if "_B08.jp2" in jp2File:
            b8aFileName = jp2File
        if "_B04.jp2" in jp2File:
            b4FileName = jp2File
    if b4FileName is None or b8aFileName is None:
        sys.exit("Could not find red or NIR images in files")

    b8a = gdal.Open(b8aFileName)
    b4 = gdal.Open(b4FileName)

    d8a = b8a.GetRasterBand(1)
    d4 = b4.GetRasterBand(1)

    # Then we need to make it readable so we'll input the data as an array.
    img_8a = d8a.ReadAsArray().astype(np.float)
    img_4 = d4.ReadAsArray().astype(np.float)

    # Next is the calculation remember [(NIR-RED)/(NIR+RED)]
    ndvi = (img_8a - img_4) / (img_8a + img_4)

    geo = b4.GetGeoTransform()
    print(geo)
    proj = b4.GetProjection()
    print(proj)
    shape = ndvi.shape
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create( "ndvi.tif", shape[1], shape[0], 1, gdal.GDT_Float32)
    ds.SetGeoTransform( geo )
    ds.SetProjection( proj )
    ds.GetRasterBand(1).WriteArray(ndvi)

    footprintGeometryWKT = generic.getDatasetFootprint(ds)

    tempFilePath = outputdirectory + '/temp.tiff';
    ds = gdal.Translate(tempFilePath, ds, format = 'GTiff')
    executeOverviews(ds)
    outputFilePath = outputdirectory + '/productOutput.tiff'
    ds = gdal.Translate(outputFilePath, ds, format = 'GTiff')

    # a bit of clean up
    os.remove(tempFilePath)

    # now write the output json file
    product = {
        "name": "NDVI image",
        "productType": "raster",
        "SRS":"EPSG:4326",
        "envelopCoordinatesWKT": footprintGeometryWKT,
        "filePath": outputFilePath,
        "description": "NDVI image from Sentinel2 platform",
        "sldName": "ndvi"
    }
    writeOutput(outputdirectory, True, "NDVI generation using geocento process", [product])

    print("NDVI script finished for SENTINEL2 product(s) at " + inputdirectory)

def calculateNDVI(ds, red, nir):
    check = np.logical_and (red > 0, nir > 0 )
    ndvi = np.where ( check,  (nir - red ) / ( nir + red ), 0.0)
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()
    shape = ndvi.shape
    driver = gdal.GetDriverByName("GTiff")
    dst_ds = driver.Create( "ndvi.tif", shape[1], shape[0], 1, gdal.GDT_Float32)
    dst_ds.SetGeoTransform( geo )
    dst_ds.SetProjection( proj )
    dst_ds.GetRasterBand(1).WriteArray(ndvi)
    return dst_ds

def findFiles(directory, extension):
    print("Scanning directory " + directory + " for files with extension " + extension)
    foundFiles = []
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            print("file " + name)
            if name.lower().endswith(extension):
                print("Adding file " + name + " at " + dirpath)
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


def generateWarpFile(outputDirectory, warpedFilePath, aoiwkt, ds, withAlpha = True):
    footprintGeometryWKT = generic.getDatasetFootprint(ds)
    if aoiwkt is not None:
        gdal.SetConfigOption('GDALWARP_DENSIFY_CUTLINE', 'NO')
        intersectionWKT = generic.calculateCutline(footprintGeometryWKT, aoiwkt)

        csvFileDirectory = outputDirectory
        csvFilePath = generic.createCutline(csvFileDirectory, intersectionWKT)

        gdal.Warp(warpedFilePath, ds, format = 'VRT', cutlineDSName = csvFilePath, srcNodata = 0, dstAlpha = withAlpha, cropToCutline = True, dstSRS = 'EPSG:4326', warpOptions = ['GDALWARP_DENSIFY_CUTLINE=NO'])

        return intersectionWKT
    else:
        gdal.Warp(warpedFilePath, ds, format = 'VRT', srcNodata = 0, dstAlpha = True, dstSRS = 'EPSG:4326')
        return footprintGeometryWKT

def executeOverviews(ds):
    # TODO - calculate based on the size of the image
    overviewList = [2, 4, 8, 16, 32]
    ds.BuildOverviews( "NEAREST", overviewList)

def writeOutput(directory, success, message, products):
    outputValues = {
        "success": success,
        "message": message,
        "products": products
    }
    with open(directory + '/output.json', 'w') as outfile:
        json.dump(outputValues, outfile)

def main():
    return ndviRaster(sys.argv)

if __name__ == '__main__':
    sys.exit(ndviRaster(sys.argv))
