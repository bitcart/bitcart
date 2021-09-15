set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
docker buildx build --push --platform ${BUILD_PLATFORMS} --tag mrnaif/$1:$CIRCLE_TAG --tag mrnaif/$1:test2 -f $2 .
cd ../../.circleci
set +e
