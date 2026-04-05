# Dashboard Troubleshooting Guide

## Issue: Not Seeing Website Cards on Dashboard

### ✅ Confirmed: Websites ARE in Database

```
4 websites found in database:
- ASOS (https://www.asos.com/)
- WSS (https://www.shopwss.com/)
- champssports (https://www.champssports.com)
- Champs Sports (https://www.champssports.com/)
```

### Most Likely Cause: Authentication Issue

The dashboard requires you to be **logged in** to see websites. The API endpoint `/api/websites` requires a valid JWT token.

## Quick Fix Steps

### 1. Check if You're Logged In

Open your browser's Developer Console (F12) and run:
```javascript
console.log('Token:', localStorage.getItem('access_token'));
```

**If it shows `null`:**
- You're not logged in
- Go to `/login` and log in with your credentials

**If it shows a token:**
- The token might be expired
- Try logging out and logging back in

### 2. Check Browser Console for Errors

1. Open Developer Tools (F12)
2. Go to Console tab
3. Refresh the dashboard page
4. Look for errors like:
   - `401 Unauthorized`
   - `Failed to load websites`
   - Network errors

### 3. Verify API is Working

In browser console, run:
```javascript
fetch('/api/websites', {
    headers: {
        'Authorization': 'Bearer ' + localStorage.getItem('access_token')
    }
})
.then(r => r.json())
.then(data => console.log('Websites:', data))
.catch(err => console.error('Error:', err));
```

**Expected result:** Should show array of 4 websites

**If you get 401:** Your token is invalid/expired - log in again

**If you get empty array:** Check if the user_id matches

### 4. Check User ID Match

The websites belong to a specific user. Make sure you're logged in as the correct user.

```bash
# Check which user owns the websites
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT id, user_id, name FROM websites;"
```

Then check your current user:
```javascript
// In browser console
fetch('/api/auth/me', {
    headers: {
        'Authorization': 'Bearer ' + localStorage.getItem('access_token')
    }
})
.then(r => r.json())
.then(data => console.log('Current user:', data));
```

## What I Fixed

### Added Empty State Message

The dashboard now shows a helpful message when no websites are loaded:
- "No websites configured"
- Hint to check login status
- Shows count: "(0 websites)"

### Database Schema Updated

✅ Added `discord_webhook_url` field  
✅ Added `crawl_progress` field  
✅ Migration applied successfully  

### API Endpoints Working

✅ GET `/api/websites` returns all fields  
✅ PUT `/api/websites/{id}` accepts discord_webhook_url  

## Solution

**Most likely you just need to log in:**

1. Go to `http://localhost:5000/login`
2. Enter your credentials
3. After successful login, go to `/dashboard`
4. You should now see all 4 websites

## If Still Not Working

### Check Flask Logs
```bash
docker compose logs flask --tail=100
```

Look for errors when accessing `/api/websites`

### Restart Flask
```bash
docker compose restart flask
```

### Create Test User and Login

If you don't have login credentials:

```bash
# Create a test user
docker compose exec flask python -c "
from app import create_app
from app.models import User
from app.extensions import db
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    # Check if user exists
    user = User.query.filter_by(email='test@example.com').first()
    if not user:
        user = User(
            email='test@example.com',
            password_hash=generate_password_hash('password123')
        )
        db.session.add(user)
        db.session.commit()
        print(f'Created user: {user.email} (ID: {user.id})')
    else:
        print(f'User exists: {user.email} (ID: {user.id})')
"
```

Then login with:
- Email: `test@example.com`
- Password: `password123`

### Update Website User IDs

If the websites belong to a different user, update them:

```bash
# Get your user ID first
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT id, email FROM users;"

# Update all websites to your user ID (replace 1 with your actual user_id)
docker compose exec postgres psql -U postgres -d product_tracker -c "UPDATE websites SET user_id = 1;"
```

---

## Summary

**The websites ARE saved in the database.** The issue is that you need to:

1. **Log in** to the application
2. Make sure you're logged in as the user who owns the websites
3. The dashboard will then load and display all 4 websites

The empty state message I added will help identify if it's an authentication issue.
