set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
: "${ARCH:=amd64}"
docker buildx build --progress plain --push --platform ${BUILD_PLATFORMS} --tag mrnaif/$1:$CIRCLE_TAG-$ARCH --tag mrnaif/$1:stable-$ARCH -f $2 .
cd ../../.circleci
set +e
