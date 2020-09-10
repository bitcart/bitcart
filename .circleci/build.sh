set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
docker build -t bitcartcc/$1:latest -f $2 .
docker push bitcartcc/$1:latest
cd ../../.circleci
set +e