

##
## OPEN CONNECTION
##
import swiftclient.client as swiftclient
import keystone.client as keystoneclient

# define credentials (from bluemix.net)
# { "auth_url":"https://identity.open.softlayer.com", "project":"xxx", "project_id":"xxx", "region":"dallas", "user_id":"xxx", "domain_id":"xxx", "domain_name":"xxx", "username":"xxx", "password":"xxx", "tenantId":"xxx" }

credentials = {
  "auth_url": "https://identity.open.softlayer.com",
  "project": "object_storage_7cc5a054_f7e1_436b_8afc_bf204239976c",
  "projectId": "d4217fcb8f5b45ef9dc360463428f7f4",
  "region": "dallas",
  "userId": "424441b4a9b24a78923256701c95f26c",
  "username": "admin_4d5b9ff81e946dcd029fd84889671e899d9c15cc",
  "password": "d8VY3xX=s/XtWqNo",
  "domainId": "e3c02da8d06f46849be963f49238b9a5",
  "domainName": "954767",
  "role": "admin"
}
# export OS_USERNAME=
# export OS_PASSWORD=
# export OS_AUTH_URL=https://identity.open.softlayer.com/v3/
# export OS_PROJECT_DOMAIN_NAME=
# export OS_REGION_NAME=

conn = swiftclient.Connection(
    key=credentials['password'],
    authurl=credentials['auth_url']+"/v3",
    auth_version='3',
    os_options={
        "project_id": credentials['projectId'],
        "user_id": credentials['userId'],
        "region_name": credentials['region']})

##
## CREATE CONTAINER
##

file = { "filename":"houses.csv", "container":"notebooks" }

conn.put_container(file['container'])

##
## PUT FILE
##

from StringIO import StringIO
import pandas as pd
import csv

data = pd.read_csv(file['filename'])
data.head()

conn.put_object(file['container'], file['filename'], data.to_csv(quoting=csv.QUOTE_ALL, index=False), content_type='text')

##
## READ FILE
##

# read file
obj = conn.get_object(file['container'], file['filename'])

data = pd.read_csv(StringIO(obj[1]))
data.head()

##
## COREML
##

import coremltools

# Convert a caffe model to a classifier in Core ML
# model = coremltools.converters.caffe.convert(('bvlc_alexnet.caffemodel', 'deploy.prototxt'), predicted_feature_name='class_labels.txt')

# Now save the model
# model.save('BVLCObjectClassifier.mlmodel')
