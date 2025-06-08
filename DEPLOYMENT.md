# 🚀 **Vercel Deployment Guide**

## **Prerequisites**

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Push your code to GitHub
3. **API Keys**: Get your Aviationstack API key from [aviationstack.com](https://aviationstack.com)

## **Step-by-Step Deployment**

### **1. Prepare Your Repository**

Make sure you have these files in your project root:
- `vercel.json` ✅ (already created)
- `requirements.txt` ✅ (already created)
- `api/forecast.py` ✅ (already created)
- `api/health.py` ✅ (already created)

### **2. Connect to Vercel**

1. Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. Click **"New Project"**
3. Import your GitHub repository
4. Configure the project:
   - **Framework Preset**: Select "Other"
   - **Root Directory**: Leave as "."
   - **Build Command**: `cd webapp && npm run build`
   - **Output Directory**: `webapp/dist`

### **3. Set Environment Variables**

In your Vercel project dashboard:

1. Go to **Settings** → **Environment Variables**
2. Add these variables:

```bash
# Required for flight data API
AVIATIONSTACK_KEY=your_aviationstack_api_key_here

# For the frontend to know the API URL
VITE_API_URL=https://your-vercel-app.vercel.app
```

### **4. Deploy**

1. Click **"Deploy"** in Vercel
2. Wait for the build to complete (~2-5 minutes)
3. Your app will be available at `https://your-project-name.vercel.app`

## **Testing Your Deployment**

### **API Endpoints**

Test these endpoints once deployed:

```bash
# Health check
GET https://your-app.vercel.app/api/health

# Flight forecast
GET https://your-app.vercel.app/api/forecast/DL/202/2025-01-15
```

### **Frontend**

1. Visit your Vercel URL
2. Enter a flight code (e.g., "DL202")
3. Click "Get forecast"
4. Verify the response includes all delay probabilities

## **Troubleshooting**

### **Common Issues**

1. **API Returns 500 Error**
   - Check that `AVIATIONSTACK_KEY` is set correctly
   - Verify the API key is valid and has credits

2. **Frontend Can't Connect to API**
   - Ensure `VITE_API_URL` matches your Vercel domain
   - Check CORS headers in API responses

3. **Build Fails**
   - Verify `requirements.txt` has correct dependencies
   - Check Python runtime version in `vercel.json`

### **Logs and Debugging**

1. **Function Logs**: Go to Vercel Dashboard → Functions → View logs
2. **Build Logs**: Check the deployment logs in Vercel
3. **Runtime Logs**: Use Vercel's real-time function logs

## **Performance Considerations**

### **Serverless Function Limits**

- **Execution Time**: 10 seconds on free plan, 60s on Pro
- **Memory**: 1024MB max
- **Request Size**: 4.5MB max

### **Optimizations**

1. **Simplified Models**: The deployment uses simplified models for faster response
2. **Caching**: Consider adding Redis for caching predictions
3. **CDN**: Vercel automatically provides CDN for static assets

## **Production Enhancements**

### **Database Options**

For production, consider:
- **Vercel Postgres**: For historical data
- **Planetscale**: For scalable MySQL
- **Supabase**: For PostgreSQL with real-time features

### **Monitoring**

- **Vercel Analytics**: Built-in performance monitoring
- **Sentry**: For error tracking
- **LogRocket**: For user session replay

## **Cost Estimation**

### **Vercel Pricing**
- **Hobby (Free)**: 100GB bandwidth, 6,000 serverless functions/month
- **Pro ($20/month)**: 1TB bandwidth, 600,000 serverless functions/month

### **External APIs**
- **Aviationstack**: $9.99/month for 10,000 requests
- **NOAA Weather**: Free (government API)

## **Alternative Deployment Options**

If Vercel limitations are restrictive:

1. **Railway**: Better for full Python applications
2. **Render**: Good for Docker deployments
3. **AWS Lambda**: More control over serverless functions
4. **Digital Ocean App Platform**: Simple container deployment

## **Local Development vs Production**

### **Local Setup**
```bash
# Backend
python -m uvicorn flight_delay_bayes.api.main:app --reload

# Frontend
cd webapp && npm run dev
```

### **Production URLs**
```bash
# Replace with your actual Vercel domain
API_URL=https://your-app.vercel.app/api
FRONTEND_URL=https://your-app.vercel.app
```

## **Security Considerations**

1. **API Keys**: Never commit API keys to git
2. **CORS**: Configured for all origins (*) - restrict in production
3. **Rate Limiting**: Consider adding rate limiting for API endpoints
4. **Input Validation**: All user inputs are validated

## **Support**

- **Vercel Documentation**: [vercel.com/docs](https://vercel.com/docs)
- **GitHub Issues**: Create issues in your repository
- **Vercel Community**: [vercel.com/community](https://vercel.com/community) 