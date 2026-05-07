# NPM Publishing Guide - OpenGraph AI MCP

## Ready to Publish ✅

The OpenGraph AI MCP server is fully prepared for npm publishing. Follow these steps to publish.

## Pre-Publication Checklist

- [x] TypeScript compiles without errors
- [x] All tests written and passing
- [x] Documentation complete
- [x] Package.json configured for npm
- [x] .npmignore created
- [x] License included
- [x] Git repository linked
- [x] Version set to 0.1.0

## Step 1: Prepare NPM Account

### If You Don't Have an NPM Account

```bash
# Create account at https://www.npmjs.com
npm adduser

# Verify login
npm whoami
```

### If You Already Have an NPM Account

```bash
# Login to npm
npm login

# Verify login
npm whoami
```

## Step 2: Verify Package Name Availability

```bash
# Check if 'opengraph-mcp' is available
npm view opengraph-mcp

# If not found, the package is available!
# If found, you may need to choose a different name:
# - opengraph-mcp-server
# - @yourorg/opengraph-mcp
# - opengraph-ai-mcp
```

## Step 3: Prepare for Publishing

### Update version if needed:

```bash
cd /Users/d/Documents/GitHub/opengraph-ai/mcp-server

# View current version
npm view . version

# If not 0.1.0, update it:
npm version 0.1.0
```

### Verify everything builds and tests pass:

```bash
npm run build
npm test
npm run lint
```

## Step 4: Dry Run (RECOMMENDED!)

Test the publishing process without actually publishing:

```bash
npm publish --dry-run

# Output should show:
# npm notice
# npm notice 📦  opengraph-mcp@0.1.0
# npm notice === Tarball Contents ===
# ... list of files ...
# npm notice === Tarball Details ===
```

## Step 5: Publish to NPM!

### Official Publish

```bash
npm publish

# Output will show:
# npm notice
# npm notice 📦  opengraph-mcp@0.1.0
# + opengraph-mcp@0.1.0
```

### Verify Package Published

```bash
# View on npm registry
npm view opengraph-mcp

# Visit: https://www.npmjs.com/package/opengraph-mcp
```

## Step 6: Tag Release in Git

```bash
# Tag the release
git tag -a v0.1.0 -m "Release v0.1.0 - Initial MCP server"

# Push tag to GitHub
git push origin v0.1.0

# Or push all tags
git push --tags
```

## Step 7: Create GitHub Release (Optional)

```bash
# Using GitHub CLI (if installed)
gh release create v0.1.0 --title "Version 0.1.0" --notes "Initial release of OpenGraph AI MCP server"

# Or manually at: https://github.com/your-org/opengraph-ai/releases
```

## Installation Verification

After publishing, test installation in a clean environment:

```bash
# In a temporary directory
cd /tmp
mkdir test-install
cd test-install

# Install from npm
npm init -y
npm install opengraph-mcp

# Verify installation
ls node_modules/opengraph-mcp
npx opengraph-mcp --version  # (if bin script configured)
```

## Making Updates (Future Versions)

### For Bug Fixes (0.1.1)
```bash
npm version patch
npm publish
git push --tags
```

### For New Features (0.2.0)
```bash
npm version minor
npm publish
git push --tags
```

### For Major Changes (1.0.0)
```bash
npm version major
npm publish
git push --tags
```

## Publishing Workflow with GitHub Actions

The `.github/workflows/publish-npm.yml` file automates future releases:

```bash
# Push a git tag to trigger publishing
git tag v0.1.0
git push --tags

# GitHub Actions will:
# 1. Build the package
# 2. Run tests
# 3. Publish to npm
# 4. Create GitHub release
```

To enable this workflow:

1. Go to your GitHub repository settings
2. Create a new secret `NPM_TOKEN`:
   - Go to npmjs.com → Account → Auth Tokens
   - Create a new "Publish" token
   - Copy the token
   - In GitHub: Settings → Secrets → New repository secret
   - Name: `NPM_TOKEN`
   - Value: Paste the token

## Publish Now - Quick Commands

```bash
# Navigate to mcp-server directory
cd /Users/d/Documents/GitHub/opengraph-ai/mcp-server

# Ensure everything is built and tested
npm run build
npm test

# Dry run to verify
npm publish --dry-run

# Publish!
npm publish

# Create git tag
git tag v0.1.0
git push origin v0.1.0

# Done! 🎉
# Package is now available at: https://www.npmjs.com/package/opengraph-mcp
```

## Post-Publication

### Update Documentation

```bash
# Add to main README
echo "## Installation

\`\`\`bash
npm install opengraph-mcp
\`\`\`

See [MCP Server](./mcp-server/QUICKSTART.md) for setup." >> ../README.md
```

### Announce Release

- Post on GitHub Discussions
- Announce on social media
- Add to changelog
- Notify users

### Monitor Package

```bash
# Check download statistics
npm stats opengraph-mcp

# Check for issues
npm issues opengraph-mcp

# Check version downloads
npm view opengraph-mcp version

# Check all versions
npm view opengraph-mcp versions
```

## Troubleshooting

### "You must be logged in to publish"
```bash
npm login
npm whoami  # Verify
npm publish
```

### "ERR! 403 Forbidden"
- Check if package name is already taken
- Verify npm account has publish permissions
- Try different package name

### "ERR! code EPUBLISH"
- Ensure you're in correct directory
- Check package.json exists
- Verify dist/ folder was built
- Check .npmignore isn't excluding important files

### "Package already published"
For duplicate publish to same version:
```bash
npm unpublish opengraph-mcp@0.1.0 --force
npm publish
```
⚠️ Only use for fixing mistakes!

## Security Best Practices

### 1. Use Token Authentication
```bash
npm login
# OR
npm set //registry.npmjs.org/:_authToken=your-token
```

### 2. Enable 2FA on npm account
- Go to npmjs.com → Account settings
- Enable "Authentication and writes"

### 3. Use scoped packages for teams
```json
{
  "name": "@yourorg/opengraph-mcp"
}
```

### 4. Publish only from CI/CD
```bash
# Recommended: Use GitHub Actions (already configured)
# Avoid: Publishing from local machine
```

## Next Steps

After Publishing:

1. ✅ Package available on npm: `npm install opengraph-mcp`
2. 📢 Announce release
3. 🚀 Users can integrate with Claude/Cursor
4. 🐛 Monitor for issues
5. 🔄 Plan next version features

## Resources

- npm Registry: https://www.npmjs.com/package/opengraph-mcp
- npm Docs: https://docs.npmjs.com/packages-and-modules/publishing-a-package
- SemVer: https://semver.org/
- MCP Protocol: https://modelcontextprotocol.io/

## Support

For questions about npm publishing:
- npm docs: `npm help publish`
- GitHub: Open issue in repository
- npm support: https://support.npmjs.com/

---

**Status**: ✅ Ready to publish

**Command to publish**: `npm publish`

**Package name**: `opengraph-mcp`

**Current version**: `0.1.0`
