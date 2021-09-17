set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
: "${ARCH:=amd64}"
if [ -z ${MANIFEST+x} ]; then
    docker buildx build --progress plain --push --platform ${BUILD_PLATFORMS} --tag mrnaif/$1:$CIRCLE_TAG-$ARCH --tag mrnaif/$1:stable-$ARCH -f $2 .
else
    docker buildx imagetools create -t mrnaif/$1:$CIRCLE_TAG mrnaif/$1:$CIRCLE_TAG-amd64 mrnaif/$1:$CIRCLE_TAG-arm
    docker buildx imagetools create -t mrnaif/$1:stable mrnaif/$1:stable-amd64 mrnaif/$1:stable-arm
fi
cd ../../.circleci
set +e
