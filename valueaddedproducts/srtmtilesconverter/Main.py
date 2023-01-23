import os
import requests
import json
import shapely.wkt
import shapely.geometry


def convert_tiles(args):

    file_path = args[0]

    # fetch tiles from service
    tiles_url = 'https://dwtkns.com/srtm30m/srtm30m_bounding_boxes.json'
    with requests.get(tiles_url, stream=True) as r:
        r.raise_for_status()
        tiles = []
        # use your product collection id
        product_collection_id = ''
        # parse and convert all tiles
        for feature in json.loads(r.text)['features']:
            tile = {}
            properties = feature['properties']
            data_file = properties['dataFile']
            id = data_file.split('.')[0]
            # a unique value to identify the product within the collection
            tile['id'] = id
            # name for display
            tile['name'] = id
            tile['description'] = "STRM tile of 1 minute width and length"
            tile['thumbnailUrl'] = "https://e4ftl01.cr.usgs.gov/DP133/SRTM/SRTMGL1.003/2000.02.11/" + id + ".SRTMGL1.2.jpg"
            tile['quicklookUrl'] = "https://e4ftl01.cr.usgs.gov/DP133/SRTM/SRTMGL1.003/2000.02.11/" + id + ".SRTMGL1.2.jpg"
            tile['productCollection'] = product_collection_id
            tile['coverageWKT'] = convert_geojson(feature['geometry']);
            # define time range for this item
            # format is YYYY-MM-ddTHH:mm:ssZ
            time_range = {'start': '2000-02-11T00:00:00Z', 'stop': '2000-02-22T00:00:00Z'}
            tile['timeRange'] = time_range
            # use the feature names you defined in the product type
            tile['features'] = {
                'vaccuracy': {'min': 90.0, 'max': 90.0},
                'resolution': {'min': 16.0, 'max': 16.0}
            }
            # add any extra parameters using a dictionary of strings
            tile['vendorParameters'] = {
                'dataFile': data_file
            }

            tiles.append(tile)

        with open(file_path, 'w') as f:
            json.dump(tiles, f)

def convert_geojson(geojson):
    g1 = shapely.geometry.shape(geojson)
    return g1.wkt


if __name__ == '__main__':
    import sys
    convert_tiles(sys.argv[1:])
