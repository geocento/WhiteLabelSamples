import os.path
from zipfile import ZipFile

import paramiko
from io import StringIO
import json
import os

def get_result(result):
    return "<result>" + json.dumps(result) + "</result>"


# Define your connection parameters
hostname = 'secureftp.iceye.com'
port = 22  # Default SFTP port, change if needed
username = 'geocento'
private_key_content = """-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,5A329E105DA74FA4

/FT7zPW7TGd6ER/QCoPIW9HXfJmK66K/07kNEobiXsNDsmP3pspEzoNnISvk3s0T
qPU8Qm8ver/IJzS3VTwgX0BSxTpbJ0b8O0xFydVur2NzVsyAUe0olj8uwqFot4Th
3PjLEQULAZ95V54vay53plnbNp0saRWBfLc0AKjzMI2IhQk5w8ncSUQ2HCcD5qsm
EYGRL/de62r3CULjKrfpHLjM/5UrwvSOFxw43o2RNhTyZgf05vQY6PQBgoPJXHh8
8yAR0z4Rn/zLF8ysjj7URFjkUCIIKcqvGgnZ3BaW/kQBZW+f21YoGsyT4QbKT5gS
r/0LBAAiPZz8X/qQF5WA2tXghi2j2j3dxLRfhHl4+x6M41pfFn4CEjQ+SlDb6VYX
+MNah4Nf8Z1ZXNJ7ioQ4vumI5oV41jb7iyiBOxQrWj9b260LFgn4t/58pIfE0El2
Olz0voOdyQD4lfC5i6mooPWvwuuhlRNlkSHj44deYGGAcMnsrjimIv8gnpmIjTEE
C7lAgqQE6mqu3saZuxlW7sWj5bV0clKgVUG1PHrHQAviHX6GikQZxIo4guL7HC4T
Ldbe6vyhITJknOTN7+mSeSDC7cGz1Dr61PERQiMZaI0aD2+PSq+wps7DxBCt71dC
Dyh7upsursZThlevGzKk9A1sBeb487o2PgrPWNBJTWSoY7UYkUOFeh57iehUNLTH
zewhGG7vdX7mobaf2eBKsJAn9h9b4kRA81GRPs2OwFTbsQwN7z2i94AjRKzJBPen
BjGcwUl/Yf0//+1T+8rDvlkVVM7kLkLZ95N+MKwCvJono8BYeb+saIv6LfkHna6q
7mZKReMWkriRFpUugyoe7WaMwgBiQExhTumF4exoB+xbLwrml2iAPOREm/Gh//67
CGJh48+h0NpTY+Gukd8VvXzKGojY94Aay6YvP5cEPZy23l9m5fq5Bf8jD94gtzyU
NRrEF5MOOGko3BbCnjV1UJKUBr8WK6yC0u23UtFVUIyreOMGlfXF5Y+3Z9+wS9G/
6SxW/SZLVJYmlDnQ9zhwdHMhig+h3iQo32asifQyOsMAhLuh9X2QzKLAnesn2smu
b278XMsLWA0GG2Cutm2RN0Mua5EuiwHznCzmZAIzlIlyLp2YNZxgMtKAnbVaF4qr
dnelNmJgcqLJv0YRDDCo3L791eEGvabisd5+xwLv8H8y/Iqv6k8Djsa49DKAlfHH
tpX+YIjK6I2bTptydJDsWLRY9WBkc2Nwf4EnVmP9/ZX+LWi9u/0qHrPyLyePFnng
CMd+fp+1MyJMxnmaSTlNJ0GUwObV6xm5TH957ZgtnDlD+UaV7w52YMyN6iNP2gNQ
fyoTcVgM8VfeM2CapiXsWBCTd6bLbl5cFg3k2lqZ2oi7Dy09ZBc/udNkzNBAk4bZ
PhYxLsyfsMDANg7g51Qwpr0lkFzmWH/4OGkoOZ2XMI6g15enC42L3NdVH53wpvnA
ZIRCb1oIa1SJq5dMaZzFj5owpO4bfrhl4pX7mFe6ZmCnsLUCorOm/bdG6MmJFKOC
1xbaaK2YbkMUrXtjJvNB46VP12SXMZ67rErLxS2WtjdmIFej7AK+4w==
-----END RSA PRIVATE KEY-----"""

def create_order(entityId, aoiWKT, jsonOrderParameters,
                 jsonCredentials = None,
                 callbackUrl = None,
                 sandbox = False):

    print(get_result({"payload": aoiWKT}))
    return 0

def check_status(payload,
                 jsonCredentials = None,
                 sandbox = False):
    # Create an SSH client instance
    ssh_client = paramiko.SSHClient()

    # Automatically add the server's host key (this is insecure and used for the sake of example;
    # for production, you should verify the host key)
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Load the private key from the content string
    private_key = paramiko.RSAKey(file_obj=StringIO(private_key_content), password="Holmer_Green_88")

    # Connect to the server using the private key for authentication
    ssh_client.connect(hostname, port, username, pkey=private_key)

    # Open an SFTP session
    sftp = ssh_client.open_sftp()

    order_id = payload.split("::")[0]
    task_id = payload.split("::")[1]
    remote_directory_path = order_id + "/"

    # List files in the remote directory
    files = sftp.listdir(remote_directory_path)
    print(f"Files in the remote directory: {files}")
    # Close the SFTP session and SSH client
    sftp.close()
    ssh_client.close()

    if len(files) == 0:
        print(get_result({}))
    else:
        # look for directory with task id in name
        files = list(filter(lambda value: value.endswith(f"_{task_id}"), files))
        tasking_directory_path = os.path.join(remote_directory_path, files[0]).replace("\\", "/")
        print(get_result({"url": tasking_directory_path}))

def handle_download(tasking_directory_path, filepath,
                    jsonCredentials = None,
                    sandbox = False):

    # Create an SSH client instance
    ssh_client = paramiko.SSHClient()

    # Automatically add the server's host key (this is insecure and used for the sake of example;
    # for production, you should verify the host key)
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Load the private key from the content string
    private_key = paramiko.RSAKey(file_obj=StringIO(private_key_content), password="Holmer_Green_88")

    # Connect to the server using the private key for authentication
    ssh_client.connect(hostname, port, username, pkey=private_key)

    # Open an SFTP session
    sftp = ssh_client.open_sftp()

    local_file_path = filepath
    local_directory_path = os.path.dirname(local_file_path)
    files = sftp.listdir(tasking_directory_path)
    downloaded_files = []
    # Download the files
    for file in files:
        remote_file_path = os.path.join(tasking_directory_path, file).replace("\\", "/")
        local_file_path = os.path.join(local_directory_path, file)
        print(f"Downloading {remote_file_path} to {local_file_path}")
        sftp.get(remote_file_path, local_file_path)
        downloaded_files.append(local_file_path)

    print('Now zipping files')
    # now zip the downloaded files
    with ZipFile(filepath, 'w') as zip_object:
        for file in downloaded_files:
            zip_object.write(file)

    # Close the SFTP session and SSH client
    sftp.close()
    ssh_client.close()

    print(get_result({"filePath": filepath}))

create_order(None, 'samples::96465', None)

check_status('sample::96465')

check_status('samples::96465')

handle_download('samples/SLF_1926177_96465', '/tmp/iceye/tests/output.zip')
