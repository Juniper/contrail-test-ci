#!/usr/bin/env bash

source tools/common.sh

config_file="sanity_params.ini"
contrail_fab_path='/opt/contrail/utils'

export PYTHONPATH=$PATH:$PWD:$PWD/fixtures;
prepare

#Verify rally exists, else install rally
if [ $(type rally >/dev/null 2>&1; echo $?) = 0 ]; then
        echo 'rally exists'
else
        echo 'rally doesnt exist'
        exit 1
fi

python ./rally/gen_deploy_json.py
rally deployment create --filename /existing.json --name existing_cloud

## Pick file from the scenario directory and execute each scenarios 
## Generate report in html
## store it in some location
for file in ./rally/scenarios/*.json
do
    output=$(rally task start $file | grep -E "rally task report [0-9a-z\-]+ --out output.html")
    echo ${output/output/$(expr match "$file" '[a-z\./]*/\([a-z\-]*\).json')}
    ${output/output/report\/$(expr match "$file" '[a-z\./]*/\([a-z\-]*\).json')}
    ##ls $file
done

