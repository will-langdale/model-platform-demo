# 🍨 Model platform demo

A demo to show two ways to host machine learning models with a simple authentication layer.

We demonstrate two proxy options over a few simple models:

1. [APISIX](https://apisix.apache.org/) with JWT auth and route-level allow lists
2. [HAWK proxy](./hawk-proxy/README.md) with HAWK auth and route-level allow lists

And two deployment paradigms:

1. As standalone containers, using Docker, as if backed by [ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html)
2. [🚧 Planned] On a cluster, using Kubernetes, as if backed by [EKS](https://aws.amazon.com/eks/)

Each incoming service authenticates to the proxy, and each route declares which services can reach which model.

## Requirements

* [just](https://github.com/casey/just) for task running
* [uv](https://docs.astral.sh/uv/) for Python scripts used in the dummy images and smoke tests
* [Docker](https://www.docker.com/) (or [podman](https://podman.io/)) for the local container demo
* [🚧 Planned] [minikube](https://minikube.sigs.k8s.io/docs/), [helm](https://helm.sh/) and [kubectl](https://kubernetes.io/docs/reference/kubectl/) (comes with minikube) for the local cluster demo


## Quickstart

Generate JWT keys and HAWK shared keys.

```shell
just keygen
```

### APISIX

Start the docker containers.

```shell
just docker apisix
```

Run the smoke tests.

```shell
just test --apisix
```

### HAWK

Start the docker containers.

```shell
just docker hawk
```

Run the smoke tests.

```shell
just test --hawk
```

## Architecture

### Authentication and authorisation

Authentication and authorisation are handled by the selected proxy. Models never see credentials or make auth decisions.

- **Authentication** uses APISIX's `jwt-auth` plugin configured for RS256. Each consumer service holds an RSA private key and signs its own JWTs.
- **Authorisation** uses APISIX's `consumer-restriction` plugin, configured as a whitelist on each route.
- **Authentication** for HAWK uses shared keys per service and signed request headers.
- **Authorisation** for HAWK uses `allowed_consumers` on each route in `docker/hawk/config.yaml`.

### Consumer permission matrix

| Consumer    | sentiment | regression | classification |
|-------------|-----------|------------|----------------|
| service-a   | ✓         | ✓          | ✗              |
| service-b   | ✗         | ✗          | ✓              |
| service-c   | ✓         | ✗          | ✓              |
