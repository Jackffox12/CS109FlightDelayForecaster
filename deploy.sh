#!/bin/bash

# 🚀 Quick Vercel Deployment Script for Flight Delay Forecaster

echo "🚀 Preparing Flight Delay Forecaster for Vercel deployment..."

# Check if required files exist
echo "📋 Checking required files..."

required_files=("vercel.json" "requirements.txt" "api/forecast.py" "api/health.py" "webapp/package.json")
missing_files=()

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        missing_files+=("$file")
    fi
done

if [[ ${#missing_files[@]} -gt 0 ]]; then
    echo "❌ Missing required files:"
    printf '   - %s\n' "${missing_files[@]}"
    echo "Please create these files before deploying."
    exit 1
fi

echo "✅ All required files present"

# Check if webapp dependencies are installed
echo "📦 Checking webapp dependencies..."
if [[ ! -d "webapp/node_modules" ]]; then
    echo "Installing webapp dependencies..."
    cd webapp && npm install && cd ..
else
    echo "✅ Webapp dependencies already installed"
fi

# Test local build
echo "🔨 Testing local build..."
cd webapp
if npm run build; then
    echo "✅ Local build successful"
    cd ..
else
    echo "❌ Local build failed. Fix build errors before deploying."
    cd ..
    exit 1
fi

# Check if git repo is clean
echo "📝 Checking git status..."
if [[ -n $(git status --porcelain) ]]; then
    echo "⚠️  You have uncommitted changes. Commit them before deploying:"
    git status --short
    echo ""
    echo "Run: git add . && git commit -m 'Prepare for Vercel deployment'"
fi

echo ""
echo "🎯 Ready for Vercel deployment!"
echo ""
echo "Next steps:"
echo "1. Push your code to GitHub: git push origin main"
echo "2. Go to https://vercel.com/new"
echo "3. Import your GitHub repository"
echo "4. Set environment variables:"
echo "   - AVIATIONSTACK_KEY=your_api_key"
echo "   - VITE_API_URL=https://your-app.vercel.app"
echo "5. Deploy!"
echo ""
echo "📖 See DEPLOYMENT.md for detailed instructions" 