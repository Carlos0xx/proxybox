FROM ghcr.io/sagernet/sing-box:v1.13.12 AS upstream

FROM alpine:3.20

RUN apk add --no-cache ca-certificates

COPY --from=upstream /usr/local/bin/sing-box /usr/local/bin/sing-box
COPY deploy/docker/singbox-entrypoint.sh /usr/local/bin/proxybox-singbox-entrypoint

RUN chmod +x /usr/local/bin/proxybox-singbox-entrypoint

ENTRYPOINT ["/usr/local/bin/proxybox-singbox-entrypoint"]
