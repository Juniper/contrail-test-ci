#!/bin/bash -x

CONTRAIL_TEST_CI_REPO=https://github.com/juniper/contrail-test-ci
CONTRAIL_TEST_CI_BRANCH=master
CONTRAIL_FAB_REPO=https://github.com/juniper/contrail-fabric-utils
CONTRAIL_FAB_BRANCH=master
DOCKERFILE=./Dockerfile

function usage {
  cat <<EOF
Usage: $0 [OPTIONS] contrail-install-packages-http-url
Build Contrail-test ci container
  -h|--help         Print help message
  -r|--repo         Contrail-test-ci git repo, Default: github.com/juniper/contrail-test-ci.git
  -b|--branch       Contrail-test-ci git branch, Default: master
  --fab-repo        Contrail-fabric-utils git repo
  --fab-branch      Contrail-fabric-utils git branch, Default: master
  --container-tag   Docker container tag, default to contrail-test-ci-<openstack-release>:<contrail-version>
                    openstack-release and contrail-version is extracted from contrail-install-package name
                    e.g contrail-test-ci-juno:2.21-105
  -d|--dockerfile   Dockerfile path
  -e|--export       Export Container image to the path provided

  positional argument
  contrail-install-package-url  Http url to contrail_install_packages deb package

  Example:

  $0 -r https://\$GITUSER:\$GITPASS@github.com/juniper/contrail-test-ci -e /shared/containers http://nodei16/contrail-install-packages_2.21-105~juno_all.deb
EOF
}

if ! options=$(getopt -o hnr:b:u:t:d:e: -l help,no-cache,export:,dockerfile:,repo:,branch:,contrail-install-package-url:,fab-repo:,fab-branch:,container-tag: -- "$@"); then
# parse error
  usage
  exit 1
fi
eval set -- "$options"

while [ $# -gt 0 ]; do
  case "$1" in
		-h|--help) usage; exit;;
		-r|--repo) CONTRAIL_TEST_CI_REPO=$2; shift;;
		-b|--branch) CONTRAIL_TEST_CI_BRANCH=$2; shift;;
		-u|--contrail-install-package-url) CONTRAIL_INSTALL_PACKAGE_URL=$2; shift;;
		--fab-repo) CONTRAIL_FAB_REPO=$2; shift;;
		--fab-branch) CONTRAIL_FAB_BRANCH=$2; shift;;
		-t|--container-tag) CONTAINER_TAG=$2; shift;;
		-n|--no-cache) NO_CACHE=$2; shift;;
        -d|--dockerfile) DOCKERFILE=$2; shift;;
        -e|--export) EXPORT_PATH=$2; shift;;
		--) :;;
		*) contrail_install_package_url=$1;;
	esac
	shift
done

if [[ -z $contrail_install_package_url ]]; then
    echo "No contrail package url provided"; echo
    usage
    exit 1
fi

if [[ -z $CONTAINER_TAG ]]; then
    if [[ ! $contrail_install_package_url =~ http[s]*://.*/contrail-install-packages_[0-9\.\-]+~[a-zA-Z]+_all.deb ]]; then
        echo -e "Hmmm --container-tag is not provided, Trying to extract tag from contrail package url\nBad contrail package url, it should match regex http[s]*://.*/contrail-install-packages_[0-9\.\-]+~[a-zA-Z]+_all.deb"
        exit 1
    else
        contrail_version=`echo ${contrail_install_package_url##*/} | sed 's/contrail-install-packages_\([0-9\.\-]*\).*/\1/'`
        openstack_release=`echo ${contrail_install_package_url##*/} | sed 's/contrail-install-packages_[0-9\.\-]*~\([a-zA-Z]*\).*/\1/'`
        CONTAINER_TAG=contrail-test-ci-${openstack_release}:${contrail_version}
    fi
fi

# IS docker runnable?
docker  -v &> /dev/null ; rv=$?

if [ $rv -ne 0 ]; then
  echo "docker is not installed, please install docker-engine (https://docs.docker.com/engine/installation/)"
  exit 1
fi

if [[ -n $NO_CACHE ]]; then
  cache_opt='--no-cache'
fi

build_dir=`dirname  $(readlink -f ./Dockerfile)`

docker build ${cache_opt} -t ${CONTAINER_TAG} -f $DOCKERFILE \
    --build-arg CONTRAIL_INSTALL_PACKAGE_URL=$contrail_install_package_url \
    --build-arg CONTRAIL_TEST_CI_REPO=$CONTRAIL_TEST_CI_REPO  \
    --build-arg CONTRAIL_TEST_CI_BRANCH=$CONTRAIL_TEST_CI_BRANCH \
    --build-arg CONTRAIL_FAB_REPO=$CONTRAIL_FAB_REPO \
    --build-arg CONTRAIL_FAB_BRANCH=$CONTRAIL_FAB_BRANCH $build_dir ; rv=$?

if [ $rv -eq 0 ]; then
    echo "Successfully built the container image - $CONTAINER_TAG"
    if [[ -n $EXPORT_PATH ]]; then
        echo "Exporting the image to $EXPORT_PATH"
        mkdir -p $EXPORT_PATH
        docker save $CONTAINER_TAG | gzip -c > ${EXPORT_PATH}/${CONTAINER_TAG/:/-}.tar.gz; rv=$?
        if [ $rv -eq 0 ]; then
            echo "Successfully exported the image to ${EXPORT_PATH}/${CONTAINER_TAG/:/-}.tar.gz"
        fi
    fi
fi
