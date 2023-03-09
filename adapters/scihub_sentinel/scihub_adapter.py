# importing the requests library
import requests
import json
from xml.dom.minidom import parse, parseString

from docutils.nodes import status

scihub_url= 'https://scihub.copernicus.eu/dhus/odata/v1'

# a very simple adapter for ordering and downloading sentinel data from schihub
# it doesn't take into account any possible ordering parameters
# these would be passed on from the ordering options specified by the user and contained in the jsonOrderParameters object

# implementation of the methods required by the orderer

# method called when starting the process
# the adapter is expected to create the ordering request
# its returns a payload to be used by the check status in polling mode
def create_order(
                # the actual product ID
                productId,
                # the requested area of interest from the product
                # in this example we do not use this parameter, it would be better to use it to clip the product
                aoiWKT,
                # a simple json object as key value pair of parameter name and value in string format
                jsonOrderParameters,
                # the json credentials as specified in your ordering policies
                jsonCredentials = None,
                # a callback URL if the API requests one, this is not used for scihub
                # if a callback url is needed, use this URL
                # the callback url endpoint will call this adapter using the handle_callback method
                callbackUrl = None,
                # if you wish to run in sandbox mode
                # sandbox is set to True when the requesting user is an admin user
                sandbox = False):

    [user, password] = get_credentials(jsonCredentials, sandbox)

    url = get_downloadurl(productId, user, password)
    if url is None:
        # url is not available so we need to put in a LTA request
        # this will be picked up by the check status method
        print(getResult({'payload': json.dumps({'productId': productId})}))
    else:
        # product is immediately downloadable so we pass the download URL
        # this will will be picked up by the handle_download method
        print(getResult({'url': url}))
    return 0

# called on a polling basis to check the status of the order
# if the product is ready to be downloaded the method should print the URL as per {'url': url}
def check_status(
                # data passed on from the previous step with information useful for the check status, eg request id
                payload,
                jsonCredentials = None,
                sandbox = False):

    [user, password] = get_credentials(jsonCredentials, sandbox)

    # parse payload to get the product URL
    productId = json.loads(payload)['productId']
    url = get_downloadurl(productId, user, password)
    if url is None:
        print(getResult({}))
    else:
        print(getResult({'url': url}))

# called if a callback url was used with the API and has been called
# not used here
def handle_callback(
        # the payload sent by the callback
        payload,
        sandbox = False):
    None

# proceeds with the download of the file based on the URL in one of the previous steps
def handle_download(
                    # the url provided by one of the previous steps
                    url,
                    # path of the file where to store the downloaded product(s)
                    filepath,
                    jsonCredentials = None,
                    sandbox = False):

    [user, password] = get_credentials(jsonCredentials, sandbox)

    print('Downloading file at ' + filepath + ' from URL ' + url)
    with requests.get(url, auth = (user, password), stream=True) as r:
        r.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
    print(getResult({"filePath": filepath}))


# methods used for the SciHub API

def get_downloadurl(productId, user, password):
    productXMLResponse = requests.get(scihub_url + "/Products",
                                      params = {"$filter": "Name eq '" + productId + "'"},
                                      auth = (user, password))

    xmldoc = parseString(productXMLResponse.text)
    productUrl = xmldoc.getElementsByTagName('entry')[0].getElementsByTagName('id')[0].firstChild.nodeValue
    requestUrl = productUrl + "/$value"
    # check if product is in LTA or not
    if xmldoc.getElementsByTagNameNS('*', 'Online')[0].firstChild.nodeValue == 'false':
        # product is not available Online so we need to trigger a request
        # see https://scihub.copernicus.eu/userguide/LongTermArchive
        statusCode = requests.get(requestUrl, auth = (user, password)).status_code
        # the request was accepted
        if status == 202:
            return None
        else:
            print('Error with request, status code is ' + str(statusCode))
            raise Exception('The product could not be requested from the Long Term Archive')
    else:
        return requestUrl

def get_credentials(jsonCredentials, sandbox):
    scihub_username = None
    scihub_password = None
    # first check if we should use some credentials passed by the orderer
    if jsonCredentials is not None:
        try:
            # get the values using an assumed json {"scihubAPIUser": "XXX", "scihubAPIPass": "XXX"} but you can define any json you like
            scihub_username = jsonCredentials['scihubAPIUser']
            scihub_password = jsonCredentials['scihubAPIPass']
        except Exception as e:
            print(str(e))
    # if no value is available then use the default username and password
    if scihub_password is None or scihub_username is None:
        # TODO - specify your default user and password if allowed
        scihub_username = "default_scihub_api_user"
        scihub_password = "default_scihub_api_pass"

    return [scihub_username, scihub_password]

def getParameter(name, parameters):
    for parameter in parameters:
        if parameter['name'].lower() == name.lower():
            return parameter['value']
    return None

def printResult(result):
    print("<result>" + json.dumps(result) + "</result>")

def getResult(result):
    return "<result>" + json.dumps(result) + "</result>"
