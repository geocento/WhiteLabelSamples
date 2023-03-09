import requests
import json
import os
import cgi
from urllib.request import urlopen
import time

import ssl

ssl._create_default_https_context = ssl._create_unverified_context

APIUrl = "https://m2m.cr.usgs.gov/api/api/json/stable/$service"

default_userName = None
default_password = None

def create_order(entityId, aoiWKT, jsonOrderParameters,
                 jsonCredentials = None,
                 callbackUrl = None,
                 sandbox = False):

    auth_token = get_authtoken(jsonCredentials, sandbox)

    # create request
    platformName = get_plaformname(entityId)
    platformName = platformName.upper()
    print('Platform name is ' + platformName)
    # used to retrieve downloads if needed
    label = "PRODUCT_" + entityId
    #product = get_product(productId)
    if entityId[-2:] in ["00", "01", "02"]:
        entityId = entityId[:-2]
    # try with different processing levels
    for level in ["00", "01", "02"]:
        entity_id = entityId + level
        product_id = get_productid(platformName, entity_id, auth_token)
        if product_id is None:
            # skip if no product id could be found
            continue
        data = {
            "downloads": [
                {
                    "label": label,
                    "entityId": entity_id,
                    "productId": product_id
                }
            ],
            "datasetName": get_dataset(platformName),
            "downloadApplication": 'EE'
        }

        headers = {"X-Auth-Token": auth_token}
        url = getUrl("download-request")

        response = requests.get(url, headers=headers, json=data)

        result = parseResponse(response);

        result_data = result['data']
        if 'failed' in result_data and len(result_data['failed']) > 0:
            continue

        if 'availableDownloads' in result_data:
            available_downloads = result_data['availableDownloads']
            if len(available_downloads) > 0:
                print(getResult({"url": available_downloads[0]['url']}))
                return 0

        if 'preparingDownloads' in result_data:
            preparing_downloads = result_data['preparingDownloads']
            if len(preparing_downloads) > 0:
                print(getResult({"payload": json.dumps({'label': label, 'preparingDownloads': preparing_downloads})}))
                return 0


    # no download url was found
    print(getResult({"error": "No download URLs found for your dataset"}))
    return -1

def check_status(payloadvalue,
                 jsonCredentials = None,
                 sandbox = False):

    payload = json.loads(payloadvalue)
    # get the staged download
    label = payload['label']
    preparing_downloads = payload['preparingDownloads']
    download_id = preparing_downloads[0]['downloadId']

    auth_token = get_authtoken(jsonCredentials, sandbox)

    headers = {"X-Auth-Token": auth_token}
    url = getUrl("download-retrieve")

    data = {'label': label}

    response = requests.get(url, headers=headers, json=data)

    result = parseResponse(response)

    # find the matching record
    data = result['data']
    if 'available' in data:
        for download in data['available']:
            if download['downloadId'] == download_id:
                print(getResult({"url": download['url']}))


def handle_download(url, filepath,
                    jsonCredentials = None,
                    sandbox = False):

    print('Downloading file at ' + filepath + ' from URL ' + url)

    remotefile = urlopen(url)
    blah = remotefile.info()['Content-Disposition']
    value, params = cgi.parse_header(blah)
    filename = params["filename"]
    if filename is None:
        # do not change the filepath
        None
    else:
        filepath = os.path.join(os.path.dirname(filepath), filename)

    with requests.get(url, stream=True) as r:
        if r.status_code >= 300:
            print(getResult({"error": "Problem submitting order, message is: " + r.text}))
            return 0
        else:
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
    print(getResult({"filePath": filepath}))

def get_authtoken(jsonCredentials, sandbox):
    tokenFileName = 'usgsTokenFile'
    if sandbox == True:
        tokenFileName += "SandBox"
    else:
        tokenFileName += "Production"

    # check if we have a valid token first
    if os.path.isfile(tokenFileName):
        with open(tokenFileName, 'r') as infile:
            if infile is not None:
                try:
                    tokenValues = json.load(infile)
                    if tokenValues['validUntil'] > time.time() + 30:
                        return tokenValues['token']
                except Exception as e:
                    print('Error reading file ' + str(e))
                finally:
                    infile.close()

    user_name = None
    password = None
    if jsonCredentials is not None:
        try:
            user_name = jsonCredentials['username']
            password = jsonCredentials['password']
        except Exception as e:
            print(str(e))
    if user_name is None or password is None:
        raise Exception("Failed to create order, missing credential information")

    # no valid token so we need to request a new one
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    url = getUrl("login")

    response = requests.post(url, headers=headers, json={"username": user_name, "password": password})

    result = parseResponse(response);

    # check for error
    if 'error' in result:
        error = result['error']
        raise Exception(error)

    # now get the token
    token = result['data']
    # key is valid for one hour
    validUntil = time.time() + 1 * 60 * 60
    # store the response for later queries
    with open(tokenFileName, 'w+') as outfile:
        if outfile is not None:
            try:
                json.dump({'token': token, 'validUntil': validUntil}, outfile)
            except Exception as e:
                print('Error writing to token file' + str(e))
            finally:
                outfile.close()

    return token

def get_plaformname(productId):
    if productId.startswith('LC9'):
        return 'LANDSAT9'
    if productId.startswith('LC8'):
        return 'LANDSAT8'
    if productId.startswith('LE7'):
        return 'LANDSAT7'
    if productId.startswith('MOD'):
        return 'TERRA'
    if productId.startswith('MYD'):
        return 'AQUA'


def get_dataset(platform):
    if platform == 'LANDSAT7':
        return 'LANDSAT_ETM_C1'
    elif platform == 'LANDSAT8' or platform == 'LANDSAT9':
        return 'landsat_ot_c2_l1'
    elif platform == 'AQUA':
        return 'MODIS_MYD09GQ_V6'
    elif platform == 'TERRA':
        return 'MODIS_MOD09GQ_V6'

def get_productid(platform, entity_id, auth_token):
    productName = None
    if platform == 'LANDSAT8' or platform == 'LANDSAT9':
        productName = 'Product Bundle'
    elif platform.startswith('LANDSAT7'):
        return "5e83a507d6aaa3db"
    elif platform.startswith('LANDSAT-5') or platform.startswith('LANDSAT-4'):
        return "5e83d0b84df8d8c2"
    elif platform.startswith('TERRA'):
        return "5e83dd517de4d28a"
    elif platform.startswith('AQUA'):
        return "5e83d0b84df8d8c2"

    # now search for the product in the available options
    download_options = get_downloadoptions(platform, entity_id, auth_token)
    if download_options is None:
        return None
    for option in download_options:
        if productName in option['productName'] and option['available'] == True:
            return option['id']

def get_downloadoptions(platform, product_id, auth_token):
    url = getUrl("download-options")

    headers = {"X-Auth-Token": auth_token}

    payload = {'datasetName' : get_dataset(platform), 'entityIds' : product_id}

    response = requests.get(url, headers=headers, json=payload)

    result = parseResponse(response)

    print(str(result))

    return result['data']


def getUrl(service):
    return APIUrl.replace("$service", service)

def parseResponse(response):
    if response.status_code >= 300:
        raise Exception(response.text)
    else:
        return json.loads(response.text)

def getParameter(name, parameters):
    for parameter in parameters:
        if parameter['name'].lower() == name.lower():
            return parameter['value']
    return None

def printResult(result):
    print("<result>" + json.dumps(result) + "</result>")

def getResult(result):
    return "<result>" + json.dumps(result) + "</result>"
