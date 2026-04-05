# Dashboard Website Card Controls - Fixed

## Changes Made

### Previous Issues
1. **Confusing button logic** - Multiple buttons with complex visibility conditions
2. **No clear "Stop" button** - Only had "Pause" which didn't actually stop the crawl
3. **Update button hidden** - Only showed in specific states
4. **No confirmation for destructive actions**

### New Button Layout

The website cards now have **4 clear buttons** in a 2x2 grid:

```
┌─────────────┬─────────────┐
│   Start     │    Stop     │  (Row 1: Primary controls)
│   Update    │  Schedule   │  (Row 2: Secondary controls)
└─────────────┴─────────────┘
│   Configure                │  (Full width)
└────────────────────────────┘
```

### Button Behavior

#### 1. **Start Button** (Green gradient)
- **When visible**: When crawl is NOT running
- **Action**: Starts a new crawl for the website
- **Icon**: Play icon
- **Notification**: "🚀 Crawl started successfully!"

#### 2. **Stop Button** (Red gradient)
- **When visible**: When crawl IS running
- **Action**: Kills the running crawl and all related tasks
- **Confirmation**: "Are you sure you want to stop this crawl?"
- **Icon**: X icon
- **Notification**: "🛑 Crawl stopped successfully"
- **Note**: Replaces Start button when crawling

#### 3. **Update Button** (Blue)
- **When visible**: Always visible
- **Action**: Triggers a new crawl (same as Start)
- **Disabled**: When crawl is already running
- **Icon**: Refresh icon
- **Notification**: "🔄 Starting update crawl..."
- **Use case**: Quick way to refresh product data

#### 4. **Schedule Button** (Purple)
- **When visible**: Always visible
- **Action**: Opens schedule modal (coming soon)
- **Icon**: Calendar icon
- **Notification**: "📅 Schedule feature coming soon!"
- **Future**: Will allow setting up automatic crawl schedules

#### 5. **Configure Button** (Gray, full width)
- **When visible**: Always visible
- **Action**: Opens configuration modal
- **Icon**: Settings icon
- **Current**: Allows setting Discord webhook URL
- **Future**: More configuration options

---

## Technical Implementation

### Frontend Changes (`dashboard_v2.html`)

**Button Visibility Logic:**
```javascript
// Start button - show when NOT crawling
x-show="!website.is_crawling"

// Stop button - show when crawling
x-show="website.is_crawling"

// Update button - always visible, disabled when crawling
:disabled="website.is_crawling"
:class="website.is_crawling ? 'opacity-50 cursor-not-allowed' : '...'"

// Schedule button - always visible
// Configure button - always visible
```

**New killCrawl Function:**
```javascript
async killCrawl(id) {
    // 1. Ask for confirmation
    if (!confirm('Are you sure you want to stop this crawl?')) {
        return;
    }
    
    // 2. Call stop API
    const response = await fetch(`/api/websites/${id}/crawl/stop`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token }
    });
    
    // 3. Show notification
    this.addNotification('🛑 Crawl stopped successfully', 'success');
    
    // 4. Reload website data after 1 second
    setTimeout(() => this.loadWebsites(), 1000);
}
```

**Simplified updateCrawl Function:**
```javascript
async updateCrawl(id) {
    this.addNotification('🔄 Starting update crawl...', 'info');
    await this.startCrawl(id);  // Just trigger a new crawl
}
```

---

## Why Crawls Don't Start Immediately

See `QUEUE_SYSTEM_EXPLAINED.md` for full details. Summary:

### Queue Flow
```
User clicks "Start"
    ↓
Task queued to Redis (crawl_queue)
    ↓
Celery worker picks up task (if available)
    ↓
crawl_website executes
    ↓
Discovery tasks queued (scrape_queue)
    ↓
Products discovered and saved
```

### Reasons for Delays

1. **Workers are busy** - Only 2 crawl workers, 4 scrape workers
2. **Sequential processing** - `worker_prefetch_multiplier=1`
3. **Long-running tasks** - Discovery can take 40-80 seconds
4. **Database connections** - Pool limits can slow processing

### Current Capacity

**Crawl Workers:**
- Concurrency: 2
- Can handle: 2 simultaneous crawl initiations

**Scrape Workers:**
- Concurrency: 4
- Can handle: 4 simultaneous discovery/extraction tasks

**If you click "Start" on 3 websites:**
- Website 1 & 2: Start immediately
- Website 3: Waits in queue until a worker is free

---

## Testing the New Controls

### Test Scenario 1: Start a Crawl
1. Click "Start" button on any website
2. Button should change to "Stop" immediately
3. Progress bar should appear
4. Notification: "🚀 Crawl started successfully!"

### Test Scenario 2: Stop a Crawl
1. While crawl is running, click "Stop"
2. Confirmation dialog appears
3. Click "OK"
4. Notification: "🛑 Crawl stopped successfully"
5. Button changes back to "Start" after 1 second

### Test Scenario 3: Update
1. Click "Update" button
2. Notification: "🔄 Starting update crawl..."
3. Same as clicking "Start"

### Test Scenario 4: Disabled State
1. Start a crawl
2. "Update" button should become grayed out
3. Clicking it does nothing
4. After stopping, it becomes active again

---

## API Endpoints Used

### Start Crawl
```
POST /api/websites/{id}/crawl
Body: { "force_full_crawl": false }
```

### Stop Crawl
```
POST /api/websites/{id}/crawl/stop
```

### Get Website Status
```
GET /api/websites
```

---

## Future Enhancements

### Pause/Resume (Not Implemented)
- Would require backend support for pausing Celery tasks
- Complex to implement reliably
- Current "Stop" is simpler and more reliable

### Schedule Modal (Coming Soon)
- Set up recurring crawls (daily, weekly, etc.)
- Choose specific times
- Enable/disable schedules

### Progress Details
- Show which phase: "Discovering products", "Extracting details"
- Show product count: "1,234 / 5,000 products"
- Show estimated time remaining

### Queue Status
- Show position in queue: "Position 3 in queue"
- Show estimated wait time
- Show active workers count

---

## Summary

**Fixed:**
- ✅ Clear, simple button layout
- ✅ Start/Stop toggle based on crawl state
- ✅ Update button always available (disabled when crawling)
- ✅ Confirmation dialog for destructive actions
- ✅ Better notifications with emojis
- ✅ Proper error handling

**Removed:**
- ❌ Confusing conditional button logic
- ❌ "Pause" button (replaced with "Stop")
- ❌ Complex visibility conditions

**Improved:**
- 🎯 User knows exactly what each button does
- 🎯 Can't accidentally start multiple crawls
- 🎯 Clear feedback on all actions
- 🎯 Consistent button placement across all cards
