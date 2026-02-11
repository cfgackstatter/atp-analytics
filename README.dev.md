# ATP Analytics Development

## Quick Commands

### Local Development
- `make test` - Run locally with test data
- Open http://localhost:8000
- Password stored in `.admin-password.txt`

### Deployment
- `make deploy` - Full deploy to production
- `make logs` - View production logs
- `make ssh` - SSH into production

### Docker
- `make build` - Rebuild image
- `make clean` - Clean up old images

## Files Not in Git
- `.admin-password.txt` - Production password (keep safe!)

## Production Environment Variables
Set once via: `eb setenv ADMIN_PASSWORD=$(cat ./.admin-password.txt)`
