# ATP Analytics Development

## Quick Commands

### Help
- `make help` - Show all available commands

### Local Development
- `make test` - Build and run locally with test data
- `make build` - Build Docker image only (no cache)
- Open http://localhost:8000
- Password stored in `.admin-password.txt`

### Deployment
- `make deploy` - Auto-commit, push, and deploy to production
- `make logs` - Stream production logs in real-time
- `make ssh` - SSH into production instance

### Monitoring
- `make status` - Show EB environment status and environment variables
- `make logs` - Stream logs (Ctrl+C to exit)

### Cleanup
- `make clean` - Remove local Docker images and prune system

## Workflow

### Typical Development Cycle
```bash
# 1. Make code changes
# 2. Test locally
make test

# 3. Deploy (auto-commits, pushes, and deploys)
make deploy

# 4. Monitor deployment
make logs
```

### Smart Deploy Behavior

- If you have uncommitted changes: prompts for commit message
- If working tree is clean: pushes and deploys existing commits
- Never fails on "nothing to commit"

## Files Not in Git

- `.admin-password.txt` - Production password (keep safe!)
- `data/` - Local Parquet files
- `.env` - Not needed with Makefile

## Production Environment Variables

Set once via:
```bash
eb setenv ADMIN_PASSWORD=$(cat ./.admin-password.txt)
eb setenv USE_S3=true
eb setenv AWS_REGION=us-east-1
```

Verify with:
```bash
make status
```

## Troubleshooting

### Test fails locally:

- Ensure `data/` directory exists with local data
- Check `.admin-password.txt` exists
- Verify Docker is running

### Deploy fails:

- Check `eb status` shows healthy environment
- Run `make logs` to see errors
- Verify git push succeeded

### Password issues:

- Local: Check `.admin-password.txt` exists
- Production: Run `make status` to verify env vars

## Reference

All commands defined in `Makefile` - run `make help` for quick reference.