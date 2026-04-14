# Caching & CDN Patterns

Reference for `devops-aws-expert` skill — content delivery and caching strategies.

---

## CloudFront Distribution

### Basic Setup

```hcl
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = ["example.com", "www.example.com"]
  price_class         = "PriceClass_100"  # US + Europe only (cheapest)

  origin {
    domain_name              = aws_s3_bucket.static.bucket_regional_domain_name
    origin_id                = "s3-static"
    origin_access_control_id = aws_cloudfront_origin_access_control.main.id
  }

  origin {
    domain_name = aws_lb.api.dns_name
    origin_id   = "api"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Static assets (S3)
  default_cache_behavior {
    target_origin_id       = "s3-static"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 86400    # 24 hours
    max_ttl     = 31536000 # 1 year
  }

  # API requests (not cached)
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "api"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Accept", "Origin"]
      cookies { forward = "all" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # SPA routing — serve index.html for all 404s
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }
}
```

### Origin Access Control (OAC)

```hcl
resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "${local.name_prefix}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
```

- Use OAC (not OAI) — it's the newer, recommended method
- S3 bucket policy must allow CloudFront to read via OAC
- Block all public access on the S3 bucket

### Cache Behaviors

| Path | Cache | TTL | Forward |
|---|---|---|---|
| `/static/*` | Yes | 1 year | Nothing |
| `/api/*` | No | 0 | Headers, cookies, query string |
| `/_next/*` | Yes | 1 year | Nothing (hashed filenames) |
| Default (`*`) | Yes | 24 hours | Nothing |

### Cache Invalidation

```bash
# Invalidate specific paths
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/index.html" "/manifest.json"

# Invalidate all (expensive — use sparingly)
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/*"
```

**Best practices:**
- Use hashed filenames for assets (e.g., `main.abc123.js`) — never needs invalidation
- Only invalidate non-hashed files (`index.html`, `manifest.json`)
- First 1,000 invalidation paths/month are free; $0.005 per path after
- Prefer short TTLs over frequent invalidation

---

## ElastiCache

### Redis vs Memcached

| Factor | Redis | Memcached |
|---|---|---|
| Data structures | Strings, lists, sets, hashes, sorted sets | Strings only |
| Persistence | Optional (snapshots, AOF) | No |
| Replication | Yes (read replicas) | No |
| Pub/sub | Yes | No |
| Cluster mode | Yes (sharding) | Yes (auto-discovery) |
| **Use when** | Sessions, leaderboards, queues, complex caching | Simple key-value caching |

**Default choice: Redis** — more versatile, supports more use cases.

### Redis Configuration

```hcl
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "Redis cluster for ${var.project_name}"
  node_type            = var.environment == "production" ? "cache.r6g.large" : "cache.t4g.micro"
  num_cache_clusters   = var.environment == "production" ? 2 : 1

  engine_version       = "7.0"
  port                 = 6379
  parameter_group_name = "default.redis7"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  automatic_failover_enabled = var.environment == "production"
  multi_az_enabled           = var.environment == "production"

  snapshot_retention_limit = var.environment == "production" ? 7 : 0
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "mon:05:00-mon:07:00"
}
```

### Caching Patterns

**Cache-Aside (Lazy Loading):**
1. Check cache for data
2. If miss, read from database
3. Write to cache with TTL
4. Return data

**Write-Through:**
1. Write to cache AND database on every write
2. Cache is always up-to-date
3. Higher write latency, but no cache misses

**TTL Strategy:**
| Data type | TTL | Rationale |
|---|---|---|
| User sessions | 24 hours | Session duration |
| API responses | 5-60 minutes | Freshness vs performance |
| Static lookups | 1-24 hours | Rarely changes |
| Rate limit counters | 1-60 minutes | Window duration |

---

## Cloudflare Integration

When using Cloudflare in front of (or instead of) CloudFront:

### DNS Setup with Cloudflare

- Use Cloudflare as DNS provider with proxy enabled (orange cloud)
- Or use Cloudflare DNS-only (gray cloud) with CloudFront CDN behind it

### Cloudflare + AWS Architecture

```
Users → Cloudflare (DNS + WAF + DDoS) → CloudFront (CDN + caching) → ALB → ECS
```

or

```
Users → Cloudflare (DNS + CDN + WAF + DDoS) → ALB → ECS
```

### Cache Rules

- Set browser TTL and edge TTL separately
- Use Cache Rules for path-based caching policies
- Use Page Rules for redirects and security headers
- Use Cloudflare Workers for edge compute (URL rewriting, A/B testing)

### When to use Cloudflare vs CloudFront

| Factor | CloudFront | Cloudflare |
|---|---|---|
| AWS integration | Native (OAC, Lambda@Edge) | External |
| DDoS protection | Shield Standard (free) | Free tier (generous) |
| WAF | AWS WAF (paid per rule) | Free tier available |
| Cost model | Data transfer + requests | Flat fee (Pro plan) |
| **Use when** | Deep AWS integration needed | Cost-sensitive, multi-cloud |

---

## Edge Computing

### CloudFront Functions

- Lightweight (JavaScript), sub-millisecond execution
- Use for: URL rewrites, header manipulation, simple redirects
- No network access, limited to viewer request/response events

### Lambda@Edge

- Full Lambda runtime, up to 30 seconds execution
- Use for: origin selection, authentication, complex transformations
- Deployed to regional edge caches (not all edge locations)
- Higher latency and cost than CloudFront Functions
