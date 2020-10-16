set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
docker build -t bitcartcc/$1:$CIRCLE_TAG -f $2 .
docker tag bitcartcc/$1:$CIRCLE_TAG bitcartcc/$1:stable
docker push bitcartcc/$1:$CIRCLE_TAG
docker push bitcartcc/$1:stable
cd ../../.circleci
set +e