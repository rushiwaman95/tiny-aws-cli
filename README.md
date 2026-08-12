Build & run


# Build (final image ≈ 450–550 MB, vs 10 GB+ for a CUDA image)
docker build -t tiny-aws-cli:1.0 .

# Run API server
docker run --rm -p 8000:8000 --name tiny-aws tiny-aws-cli:1.0

# Test it
curl -s -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"request": "List all S3 buckets"}'

# Or run interactive CLI mode
docker run --rm -it tiny-aws-cli:1.0 python app.py --cli
