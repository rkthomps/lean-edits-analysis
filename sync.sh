#!/bin/bash

# Checks that aws is installed. 
# Checks that credentials are configured. 
BUCKET_NAME="programming-vacuum"
DATA_DIR="data"

which aws > /dev/null || { echo "aws is not installed. Please install aws-cli and configure credentials."; exit 1; }

echo "Doing sync..."
aws s3 sync s3://$BUCKET_NAME $DATA_DIR --delete
