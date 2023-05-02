set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
: "${ARCH:=amd64}"

create_manifest() {
    docker buildx imagetools create -t ${2}bitcartcc/$1:$CIRCLE_TAG ${2}bitcartcc/$1:$CIRCLE_TAG-amd64 ${2}bitcartcc/$1:$CIRCLE_TAG-arm
    docker buildx imagetools create -t ${2}bitcartcc/$1:stable ${2}bitcartcc/$1:stable-amd64 ${2}bitcartcc/$1:stable-arm
}

if [ -z ${MANIFEST+x} ]; then
    docker buildx build --progress plain --push --platform ${BUILD_PLATFORMS} --tag bitcartcc/$1:$CIRCLE_TAG-$ARCH --tag bitcartcc/$1:stable-$ARCH \
        --tag ghcr.io/bitcartcc/$1:$CIRCLE_TAG-$ARCH --tag ghcr.io/bitcartcc/$1:stable-$ARCH \
        --tag harbor.nirvati.org/bitcartcc/$1:$CIRCLE_TAG-$ARCH --tag harbor.nirvati.org/bitcartcc/$1:stable-$ARCH \
        -f $2 .
else
    create_manifest $1 ""
    create_manifest $1 "ghcr.io/"
    create_manifest $1 "harbor.nirvati.org/"
fi
cd ../../.circleci
set +e
