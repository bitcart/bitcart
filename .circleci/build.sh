set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
: "${ARCH:=amd64}"
if [ -z ${MANIFEST+x} ]; then
    docker buildx build --progress plain --push --platform ${BUILD_PLATFORMS} --tag bitcartcc/$1:$CIRCLE_TAG-$ARCH --tag bitcartcc/$1:stable-$ARCH -f $2 .
else
    docker buildx imagetools create -t bitcartcc/$1:$CIRCLE_TAG bitcartcc/$1:$CIRCLE_TAG-amd64 bitcartcc/$1:$CIRCLE_TAG-arm
    docker buildx imagetools create -t bitcartcc/$1:stable bitcartcc/$1:stable-amd64 bitcartcc/$1:stable-arm
fi
cd ../../.circleci
set +e
