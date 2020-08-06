set -e
cd ../bitcart-docker/compose
echo "Building $1 image"
docker build -t mrnaif/$1:latest -f backend.Dockerfile .
docker login --username=$DOCKER_USER --password=$DOCKER_PASS
docker push mrnaif/$1:latest
cd ../../.circleci
set +e