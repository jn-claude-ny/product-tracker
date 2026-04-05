# Website Configuration Fix

**Issue:** Dashboard not showing website crawl progress and Discord webhook configuration

**Root Cause:** Missing database fields in the Website model

## Changes Made

### 1. Database Schema Updates

**Added to `Website` model:**
- `discord_webhook_url` (String, 512) - Store Discord webhook URL per website
- `crawl_progress` (Integer, default=0) - Track crawl progress 0-100%

**Files Modified:**
- `app/models/website.py` - Added new columns
- `app/schemas/website.py` - Added fields to all schemas
- `alembic/versions/004_add_website_ui_fields.py` - Migration script

### 2. Schema Updates

**WebsiteSchema (GET responses):**
```python
discord_webhook_url = fields.Str(allow_none=True)
crawl_progress = fields.Int(dump_only=True)
```

**WebsiteCreateSchema (POST):**
```python
discord_webhook_url = fields.Str(allow_none=True)
```

**WebsiteUpdateSchema (PUT):**
```python
discord_webhook_url = fields.Str(validate=validate.Length(min=1, max=512), allow_none=True)
```

## Migration Instructions

### Run Migration

```bash
# Copy migration to container
docker compose cp alembic/versions/004_add_website_ui_fields.py flask:/app/alembic/versions/004_add_website_ui_fields.py

# Run migration
docker compose exec flask alembic upgrade head
```

### Verify Migration

```bash
# Check database schema
docker compose exec postgres psql -U postgres -d product_tracker -c "\d websites"
```

You should see:
- `discord_webhook_url` column (varchar 512)
- `crawl_progress` column (integer, default 0)

## API Behavior

### GET /api/websites
Now returns:
```json
{
  "id": 1,
  "name": "ASOS",
  "base_url": "https://www.asos.com",
  "discord_webhook_url": "https://discord.com/api/webhooks/...",
  "crawl_progress": 75,
  "product_count": 150,
  "is_crawling": true,
  ...
}
```

### PUT /api/websites/{id}
Can now update:
```json
{
  "discord_webhook_url": "https://discord.com/api/webhooks/..."
}
```

## Dashboard Features Now Working

✅ **Discord Configuration**
- Configure webhook URL per website
- Save via "Configure" modal
- Stored in database

✅ **Crawl Progress Display**
- Shows 0-100% progress bar
- Updates in real-time (when backend updates the field)
- Visual indication of crawl state

## Next Steps

### Backend Implementation Needed

**Update Crawl Tasks to Report Progress:**

```python
# In celery_app/tasks/discovery_tasks.py or crawl_tasks.py

def update_crawl_progress(website_id, progress):
    """Update crawl progress percentage"""
    website = Website.query.get(website_id)
    if website:
        website.crawl_progress = progress
        db.session.commit()

# During crawl:
update_crawl_progress(website_id, 25)  # 25% complete
update_crawl_progress(website_id, 50)  # 50% complete
update_crawl_progress(website_id, 100) # Complete
```

**Discord Notifications:**

```python
# When price changes or stock updates occur
def send_discord_notification(website_id, message):
    website = Website.query.get(website_id)
    if website and website.discord_webhook_url:
        requests.post(website.discord_webhook_url, json={
            "content": message,
            "embeds": [...]
        })
```

## Testing

### Test Discord Configuration

1. Go to dashboard
2. Click "Configure" on any website
3. Enter Discord webhook URL
4. Click "Save"
5. Verify saved in database:
   ```sql
   SELECT id, name, discord_webhook_url FROM websites;
   ```

### Test Crawl Progress (Manual)

```python
# In Flask shell
from app.models import Website
from app.extensions import db

website = Website.query.first()
website.crawl_progress = 50
db.session.commit()
```

Refresh dashboard - should show 50% progress bar.

## Status

✅ Database schema updated  
✅ Models updated  
✅ Schemas updated  
✅ Migration created  
⏳ Migration needs to be run  
⏳ Backend crawl tasks need progress updates  
⏳ Discord notification integration needed  

---

**The dashboard will now correctly display and save website configurations once the migration is run.**
