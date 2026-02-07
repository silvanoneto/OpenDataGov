# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app

COPY services/gateway/go.mod ./
# No go.sum needed (no external dependencies)

COPY services/gateway/ .

RUN CGO_ENABLED=0 GOOS=linux go build -o /gateway .

# Runtime stage
FROM alpine:3.19

RUN apk --no-cache add ca-certificates \
    && addgroup -S gateway \
    && adduser -S gateway -G gateway

WORKDIR /app

COPY --from=builder /gateway .

RUN chown -R gateway:gateway /app

USER gateway

EXPOSE 8080

ENTRYPOINT ["./gateway"]
