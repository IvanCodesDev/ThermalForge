#!/bin/sh
set -eu

awslocal s3api head-bucket --bucket thermalforge-artifacts >/dev/null 2>&1 \
  || awslocal s3api create-bucket --bucket thermalforge-artifacts >/dev/null
