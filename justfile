services := "service_a service_b service_c"

# Generate RSA keypairs
keygen:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p test/keys
    for svc in {{services}}; do
        openssl genrsa -out test/keys/$svc-private.pem 2048 2>/dev/null
        openssl rsa -in test/keys/$svc-private.pem -pubout -out test/keys/$svc-public.pem 2>/dev/null
    done
    
    > test/keys/.env
    for svc in {{services}}; do
        key_var=$(echo $svc | tr '[:lower:]-' '[:upper:]_')_PUBLIC_KEY
        printf "%s=\"%s\"\n" "$key_var" "$(cat test/keys/$svc-public.pem)" >> test/keys/.env
    done

# Bring docker up
docker:
    docker compose -f docker/docker-compose.yaml up -d

# Run smoke tests
test:
    uv run test/smoke.py
