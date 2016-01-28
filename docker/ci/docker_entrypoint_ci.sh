#!/bin/bash

function usage {
    cat <<EOF
Usage: $0 [OPTIONS]

Run contrail ci tests in container

  -h  Print help
  -t  Testbed file, Default: /opt/contrail/utils/fabfile/testbeds/testbed.py
  -p  contrail fab utils path. Default: /opt/contrail/utils

EOF
}

while getopts "ht:p:" opt; do
  case $opt in
    h)
      usage
      exit
      ;;
    t)
      testbed_input=$OPTARG
      ;;
    p)
      contrail_fabpath_input=$OPTARG
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done

TESTBED=${testbed_input:-${TESTBED:-'/opt/contrail/utils/fabfile/testbeds/testbed.py'}}
CONTRAIL_FABPATH=${contrail_fabpath_input:-${CONTRAIL_FABPATH:-'/opt/contrail/utils'}}

if [[ ( ! -f /contrail-test/sanity_params.ini || ! -f /contrail-test/sanity_testbed.json ) && ! -f $TESTBED ]]; then
    echo "ERROR! Either testbed file or sanity_params.ini or sanity_testbed.json under /contrail-test is required.
          you probably forgot to attach them as volumes"
    exit 100
fi

if [ ! $TESTBED -ef ${CONTRAIL_FABPATH}/fabfile/testbeds/testbed.py ]; then
    mkdir -p ${CONTRAIL_FABPATH}/fabfile/testbeds/
    cp $TESTBED ${CONTRAIL_FABPATH}/fabfile/testbeds/testbed.py
fi

cd /contrail-test
./run_ci.sh --contrail-fab-path $CONTRAIL_FABPATH
