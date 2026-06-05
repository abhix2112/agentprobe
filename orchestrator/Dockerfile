# Build context is the REPO ROOT (see docker-compose.yml) so that the layout
# mirrors the repo: Cargo manifest at /app/orchestrator, migrations at
# /app/migrations. This keeps sqlx::migrate!("../migrations") valid both here
# and in local `cargo` builds.
FROM rust:1.82-slim AS builder
WORKDIR /app/orchestrator
RUN apt-get update && apt-get install -y pkg-config && rm -rf /var/lib/apt/lists/*

# Cache dependencies against just the manifest.
COPY orchestrator/Cargo.toml ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release || true
RUN rm -rf src

# Real source + migrations (referenced by sqlx::migrate! at compile time).
COPY orchestrator/src ./src
COPY migrations /app/migrations
RUN cargo build --release

# Runtime
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/orchestrator/target/release/orchestrator /usr/local/bin/orchestrator
COPY migrations /app/migrations
EXPOSE 8080
CMD ["orchestrator"]
