services := "service_a service_b service_c"

# Generate RSA keypairs and HAWK shared keys
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

    for svc in {{services}}; do
        key_var=$(echo $svc | tr '[:lower:]-' '[:upper:]_')_HAWK_KEY
        printf "%s=\"%s\"\n" "$key_var" "$(openssl rand -hex 32)" >> test/keys/.env
    done

# Bring docker up
docker profile *ARGS:
    docker compose -f docker/docker-compose.yaml --profile "{{profile}}" up -d {{ARGS}}

# Run smoke tests
test *ARGS:
    uv run test/smoke.py {{ARGS}}
