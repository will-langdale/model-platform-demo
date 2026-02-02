# 🍨 Model platform demo

A demo to show two ways to host machine learning models with a simple authentication layer.

We demonstrate an [APISIX](https://apisix.apache.org/) API gateway over a few simple models, deployed using two paradigms:

1. As standalone containers, using Docker, as if backed by [ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html)
2. [🚧 Planned] On a cluster, using Kubernetes, as if backed by [EKS](https://aws.amazon.com/eks/)

Each incoming service authenticates with a self-signed JWT, and we declare which models the service can access in code.

## Requirements

* [just](https://github.com/casey/just) for task running
* [uv](https://docs.astral.sh/uv/) for Python scripts used in the dummy images and smoke tests
* [Docker](https://www.docker.com/) (or [podman](https://podman.io/)) for the local container demo
* [🚧 Planned] [minikube](https://minikube.sigs.k8s.io/docs/), [helm](https://helm.sh/) and [kubectl](https://kubernetes.io/docs/reference/kubectl/) (comes with minikube) for the local cluster demo


## Quickstart

### Docker

```bash
# Generate keys 
just keygen

# Start services
just docker

# Run smoke tests
just test
```

## Architecture

### Authentication and authorisation

Authentication and authorization are handled entirely by APISIX. Models never see tokens or make auth decisions.

- **Authentication** uses APISIX's `jwt-auth` plugin configured for RS256. Each consumer service holds an RSA private key and signs its own JWTs.
- **Authorisation** uses APISIX's `consumer-restriction` plugin, configured as a whitelist on each route.

### Consumer permission matrix

| Consumer    | sentiment | regression | classification |
|-------------|-----------|------------|----------------|
| service-a   | ✓         | ✓          | ✗              |
| service-b   | ✗         | ✗          | ✓              |
| service-c   | ✓         | ✗          | ✓              |
