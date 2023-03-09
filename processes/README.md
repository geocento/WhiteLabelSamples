This is a repository of various example processes, including a true colour process for publishing raw products into tiff files which can be used by the map viewer.

Processes can be created in your white label instance using the "process" tab of the administration application.

A process is defined by its parameters and a corresponding docker image which is to be uploaded separately to the WL's registry. Instructions on how to do this are provided withing the WL admin process tab page.

The process parameters are as follows:

- name, description and tags
- input manifest, a json structure specifying the acceptable inputs to the process
- output manifest, a json structure specifying the expected output(s) of the process
- parameters, list of parameters your process can take to customise the processing
- resources policy, the type of machine and storage space to use based on the input file size
- commercial policy, define if the process is available to others or not. If yes you need to define your pricing policy, licensing terms, an explanation and an icon for marketing purposes.

Once the process is registered through the WL admin process tab, instructions will be displayed below on how to upload the docker image to the WL registry. Use your user's credentials for the docker login.

When your process is being used in the WL application, the docker image will be called with the following parameters 
   1) input directory - where the input data to process is stored
   2) output directory - where the output of your process is to be written
   3) the process parameters as --parameterName=parameterValue
   4) the input product specification as --productSpecifications={json structure}

The input data to process will be contained in the input folder. 
Any output data to be saved as a result of the processing should be stored in the output directory. 
The output directory is expected to contain a "output.json" file and all the files your process has generated. This file has the following structure
```
{
    "success": <boolean, success or not>,
    "message": <information on the process, will be displayed in the application>,
    "products": [
        {
            "name": <name to be used in the application>,
            "filePath": <the local path of the product, can be a directory or a single file>,
            "envelopCoordinatesWKT": <the bounds of the product as a polygon in WKT format>,
            "SRS": <the projection used for the WKT>,
            "description": <information on the product generated, will be displayed in the application>
            "publish": <boolean, whether the product should be published in the WL map server>,
            "publishFilePath": <the relative file path to the product which should be used for publishing>,
            "publishSLD": <the SLD to be used for publishing the file>
         },
         {
            ...
         }
    ]
}
```
When the process is completed, the WL service will fetch the output.json file and scan the products to save. If the product file path is a file it will be zipped and saved. If the product file path is a directory, the whole content of the directory will be zipped and saved.

Once the products are saved and uploaded to the application. The WL process will scan the products to see if they need publishing. If publishing is set to true, the process will send the product zip file to the map server, together with the sld and the file path to publish. For instance, if the product is a zipped shapefile folder, the file path should point to the .shp file and the SLD to an SLD suitable for vector rendering. Your process SLDs can be uploaded via the process tab in the admin application.

The size of the machine running the docker image is specified by the resources rule in the proces definition. The rules are based on the (zipped) file input size, you can specify a machine type and storage amount per interval of size. When the process is triggered the system needs to start the machine and load the process' image. This can take from one to two minutes depending on the docker image size of your process.
