import sys, os, json, re, math, shutil

from osgeo import gdal, osr, ogr

# add for gdal scripts support
sys.path.append('/usr/bin/')
# add to import common directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))
import generic
import gdal_pansharpen

import numpy as np
from scipy.ndimage.filters import uniform_filter
from scipy.ndimage.measurements import variance

import zipfile

import requests

import warnings
warnings.filterwarnings("ignore")

tmpfolder = '/tmp/iceye/'

tiles_shapefile='data/srtm_grid_1deg.shp'

def Usage():
    print('Usage: trueColour(args)')


def trueColour(input_directory, output_directory, productSpecifications = None):

    print("Product specifications: " + str(productSpecifications))
    print("Shape file is present ", os.path.exists(tiles_shapefile))

    products = []

    # prepare directories
    if os.path.exists(tmpfolder):
        clear_directory(tmpfolder)
    else:
        os.makedirs(tmpfolder)
    os.makedirs(os.path.join(tmpfolder, 'zip'))

    # look for tif files
    files = generic.findFilesRegexp(input_directory, '.+(.tif$)')

    # process files
    for file in files:
        despeckled_raster = despeckle_file(file)
        # check the footprint
        # now orthorectify data
        ds_despeckled = gdal.Open(despeckled_raster)
        product_footprint_wkt = generic.getDatasetFootprint(ds_despeckled)
        # calculate scale params using the despeckle file
        [scaleParams, exponents] = generic.get_cumulative_scale_params(ds_despeckled, max_scale = 255, num_bands = 1)

        # get matching DEM
        demfiles = download_matching_dems(product_footprint_wkt)
        # turn dem files to tiff and project in wgs84
        demfile = make_wgs84_tif_demfile(demfiles)

        print('Orthorectifying the file')
        resultfile = os.path.join(tmpfolder, "orthofile.tif")
        ds = gdal.Warp(resultfile, ds_despeckled, transformerOptions=['RPC_DEM=' + demfile])
        ds_despeckled = None

        print('Scaling and translating to tiff file')
        scaled_resultfile = os.path.join(tmpfolder, "scaled_orthofile.tif")
        ds_scaled = gdal.Translate(scaled_resultfile, ds, outputType = gdal.GDT_Byte, scaleParams = scaleParams, exponents = [0.5], format = 'GTiff')
        ds = None

        print('Generate overviews')
        generic.executeOverviews(ds_scaled)

        print('Save with overviews')
        file_name = 'productOutput.tiff'
        output_file_path = os.path.join(output_directory, file_name)
        gdal.Translate(output_file_path, ds_scaled, format = 'GTiff')

        # now write the output json file
        product = {
            "name": "Display image",
            "productType": "raster",
            "SRS":"EPSG:4326",
            "envelopCoordinatesWKT": product_footprint_wkt,
            "filePath": output_file_path,
            "description": "Display image for Iceye platform",
            "publish": True,
            "publishFilePath": file_name,
            "publishSLD": "raster"
        }
        products.append(product)

    generic.writeOutput(output_directory, True, "Display image generation for Iceye product using geocento process", products)


def despeckle_file(file):
    ds = gdal.Open(file)
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()
    # now despeckle the file using a 5 x 5 Lee filter
    # check image size and if needed work in chunks
    srcband = ds.GetRasterBand(1)
    width = srcband.XSize
    height = srcband.YSize
    image_size = width * height
    threshold = 1E8
    chunks = int(math.ceil(image_size / threshold))
    chunk_height = float(height) / chunks

    # create output raster
    despeckled_raster = os.path.join(tmpfolder, "despeckled.tif")
    driver = gdal.GetDriverByName("GTiff")
    outputds = driver.Create(despeckled_raster, width, height, 1, gdal.GDT_Float32)
    outputband = outputds.GetRasterBand(1)
    outputds.SetGeoTransform( geo )
    outputds.SetProjection( proj )
    outputds.SetGCPs(ds.GetGCPs(), ds.GetGCPProjection())
    outputds.SetMetadata(ds.GetMetadata('RPC'), 'RPC')

    # do calculations over chunks
    print("Apply despeckling on image with width ", width, " height ", height, " using ", chunks, " chunks of height ", chunk_height)
    for chunk in range(0, chunks):
        start_height = int(math.floor(chunk * chunk_height))
        stop_height = int(min(math.floor((chunk + 1) * chunk_height), height))
        print("Apply Lee despeckling for image values between ", start_height, " and ", stop_height)
        leewindow_size = 5
        # add some margins to the top and bottom to avoid border artefacts
        image_bottom_margin = 0
        if start_height > 0:
            image_bottom_margin = leewindow_size
        image_top_margin = 0
        if stop_height < height:
            image_top_margin = leewindow_size
        image = srcband.ReadAsArray(0, start_height - image_bottom_margin, width, (stop_height - start_height) + image_bottom_margin + image_top_margin).astype(float)
        output = lee_filter(image, 5)
        # resize array
        output = output[image_bottom_margin:(output.shape[0] - image_top_margin),:]
        print('Writing output ' + str(output.shape) + ' with min ' + str(np.amin(output)) + ' to output band at [0, ' + str(start_height) + ']')
        outputband.WriteArray(output, 0, start_height)
        # free arrays
        image = None
        output = None
    # free datasets
    ds = None
    outputds = None

    return despeckled_raster

def lee_filter(img, size):
    img_mean = uniform_filter(img, (size, size))
    img_sqr_mean = uniform_filter(img**2, (size, size))
    img_variance = img_sqr_mean - img_mean**2

    overall_variance = variance(img)

    img_weights = img_variance / (img_variance + overall_variance)
    img_output = img_mean + img_weights * (img - img_mean)
    return img_output

def make_wgs84_tif_demfile(zipped_demfiles):
    unzip_directory = os.path.join(tmpfolder, 'zip')
    # clear unzip directory first
    clear_directory(unzip_directory)
    for demfile in zipped_demfiles:
        if os.path.basename(demfile).endswith(".zip"):
            with zipfile.ZipFile(demfile, 'r') as zip_ref:
                zip_ref.extractall(unzip_directory)
    demfiles = generic.findFiles(tmpfolder, 'hgt')

    mosaicdem_file = os.path.join(tmpfolder, "demmosaic.tif")
    ds = gdal.Warp(mosaicdem_file, demfiles, format="GTiff", dstSRS = '+proj=longlat +datum=WGS84 +no_def')
    ds = None

    return mosaicdem_file


def download_matching_dems(footprint_wkt):
    footprint_geom = ogr.CreateGeometryFromWkt(footprint_wkt)
    driver  = ogr.GetDriverByName("ESRI Shapefile")
    shpfile = driver.Open(tiles_shapefile)
    tiles = shpfile.GetLayer()
    dem_files = []
    # find intersections
    for tile in tiles:
        tile_geom = tile.GetGeometryRef()
        if tile_geom.Intersects(footprint_geom):
            dem_files.append(download_demfile_entity(tile.GetField('id')))

    return dem_files

def download_demfile_entity(tileid):
    file_name = tileid + ".SRTMGL3.hgt.zip"
    filepath = os.path.join(tmpfolder, file_name)
    url = "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL3.003/2000.02.11/" + file_name
    requests.get('https://urs.earthdata.nasa.gov/oauth/token', auth=(default_userName, default_password))

    requests.session()
    response = requests.get(url, auth=(default_userName, default_password), allow_redirects=False)
    url = response.headers.get('Location')
    with requests.get(url, auth=(default_userName, default_password), stream=True) as r:
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)

    return filepath


def clear_directory(directory):
    with os.scandir(directory) as entries:
        for entry in entries:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)


if __name__ == '__main__':
    generic.run_with_args(trueColour)
