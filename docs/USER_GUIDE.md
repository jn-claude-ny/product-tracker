# Product Tracker — User Guide

> **No technical knowledge required.** This guide walks you through everything you need to use Product Tracker, from logging in to receiving your first Discord alert.

---

## What is Product Tracker?

Product Tracker monitors sneakers and clothing across **ASOS**, **Shop WSS**, and **Champs Sports** for you — 24/7. It checks prices and stock, and sends you a Discord message the moment something you care about changes.

**What it can do for you:**
- Tell you when a price drops (or increases) on a specific product
- Notify you the moment a specific size comes back in stock
- Show you all products from all three sites in one place
- Let you filter for new arrivals, sale items, and stock status

---

## Table of Contents

1. [Signing In](#1-signing-in)
2. [The Dashboard](#2-the-dashboard)
3. [Importing Products (Crawling)](#3-importing-products-crawling)
4. [Browsing Products](#4-browsing-products)
5. [Tracking a Product](#5-tracking-a-product)
6. [Your Tracked Products](#6-your-tracked-products)
7. [Discord Alerts](#7-discord-alerts)
8. [Tips & Tricks](#8-tips--tricks)

---

## 1. Signing In

Open the app in your browser and you'll land on the sign-in page. Enter your email and password and click **Sign In**.

![Sign in screen](screenshots/login.png)

> If you don't have an account yet, click **"Don't have an account? Create one"** at the bottom of the form.

---

## 2. The Dashboard

After signing in you'll see the main dashboard. This is your home base.

![Dashboard](screenshots/websites_info.png)

Here's what you're looking at:

| Card | What it means |
|---|---|
| **Total Products** | How many products have been imported so far across all sites |
| **Websites** | The 3 supported sites (ASOS, Champs Sports, WSS) |
| **Active Crawls** | How many import jobs are currently running |
| **Tracked Products** | Products you are personally watching |

Below the stats you'll see a card for each website. Each card shows:
- When it was **last updated**
- How many products it has imported and the **progress bar**
- Buttons to **Update**, **Schedule**, and **Configure** it

---

## 3. Importing Products (Crawling)

Before you can browse or track products, the app needs to import them from each website. This is called a **crawl**.

### How to run a crawl

1. On the Dashboard, find the website card (e.g. **ASOS**)
2. Click the **Update** button

![Dashboard with websites](screenshots/websites_info.png)

The progress bar will fill up as products come in. A full crawl can take several minutes — you don't need to stay on the page, it runs in the background.

> **You only need to do this once.** After that, you can schedule automatic updates using the **Schedule** button.

### Setting up a Discord webhook (to receive alerts)

1. Click **Configure** on any website card
2. Paste your **Discord webhook URL** into the field
3. Save

> **How to get a Discord webhook URL:** In Discord, go to your server → pick a channel → click the gear icon (Edit Channel) → Integrations → Webhooks → New Webhook → Copy Webhook URL.

---

## 4. Browsing Products

Click **Products** in the top navigation bar to see everything that has been imported.

![Products page](screenshots/products.png)

Each product card shows:
- Product image, name, and brand
- Current price
- Stock status badge (**InStock** / **OutOfStock** / **LowStock**)
- Inventory count when available

### Searching and Filtering

Use the bar at the top to narrow things down.

![Search and filter bar](screenshots/Search_and_filters.png)

| Filter | What it does |
|---|---|
| **Search box** | Type a name, brand, or keyword |
| **All Websites** | Show only ASOS, only Champs, or only WSS |
| **All Genders** | Men / Women / Unisex |
| **All Stock** | In Stock / Out of Stock / Low Stock (under 50 units) |
| **Price sort** | Sort by price high-to-low or low-to-high |

You can also toggle the quick-filter buttons:

![New and sale badge filters](screenshots/sale_and_new_filters.png)

- **🆕 New Arrivals** — products flagged as new by the retailer
- **🔥 On Sale** — products currently on sale

When multiple filters are active at once:

![All filters active](screenshots/all_filters.png)

Click **Clear Filters** to reset everything.

---

## 5. Tracking a Product

Tracking a product tells the app to watch it for you and send you a Discord alert when something changes.

### Step 1 — Find the product and click Track

On any product card, click the **Track** button.

![Track button on product card](screenshots/products.png)

A dialog will appear:

![Track product dialog](screenshots/Track_product.png)

---

### Step 2 — Set a Price Alert (optional)

You'll see the **current price** of the product. Choose whether you want to be alerted when the price goes **up** or **down** from that price.

**Alert me when the price drops** (Decrease selected):

![Price decrease alert](screenshots/Track_price_decrease.png)

**Alert me when the price goes up** (Increase selected):

![Price increase alert](screenshots/Track_price_increase.png)

> Leave both unselected if you only care about stock, not price.

---

### Step 3 — Set Availability Filter (optional)

Choose what stock state should trigger an alert.

![Availability filter](screenshots/Track_availability.png)

| Option | When you'd use it |
|---|---|
| **Any** | Alert me no matter what the stock status is |
| **In Stock Only** | Only alert when the product (or a tracked size) is available |
| **Out of Stock Only** | Alert when it goes out of stock |
| **Low Stock Only** | Alert when inventory drops below 50 units |

---

### Step 4 — Choose a Priority

Priority controls **how quickly** the app re-checks that product.

![Priority selector](screenshots/Track_priority.png)

| Priority | Re-check speed | Best used for |
|---|---|---|
| ⚡ **Instant** | Right now, on demand | Manual one-off checks |
| 🔴 **Urgent** | ~5 minutes | High-demand drops, limited releases |
| 🟠 **High** | ~15 minutes | Products you really want |
| 🟡 **Moderate** | ~30 minutes | General tracking |
| 🟢 **Normal** | ~1 hour | Casual watching |

> Higher priority = faster alerts, but uses more server resources. Use **Urgent** sparingly.

---

### Step 5 — Set a Check Schedule

The schedule is how often the app does a **routine re-check** on top of the priority setting.

![Schedule selector](screenshots/Track_schedule.png)

Options: **Every Hour**, **Every 6 Hours**, **Every 12 Hours**, **Daily**, **Weekly**.

For most products **Daily** is fine. Use **Every Hour** or **Every 6 Hours** for restocks you're closely watching.

---

### Step 6 — Click Start Tracking

Hit the **Start Tracking** button and you're done. The product will now appear in your tracked products list on the dashboard.

---

## 6. Your Tracked Products

On the Dashboard, scroll down to see all the products you are tracking.

![Tracked products list](screenshots/tracked_products.png)

Each row shows:
- **Product image, name, brand, and current price**
- **Priority badge** (now / high / etc.)
- **Stock badge** (InStock / OutOfStock)
- **What you're tracking** — e.g. "Price Drop from $99999.00" or a list of sizes
- **Size availability grid** — each size shows a ✅ (in stock) or ✗ (out of stock)
- **Check schedule** and **Next check countdown**
- A **Run Now** button to trigger an immediate check

### Run Now

Click **Run Now** next to any tracked product to force an immediate scrape and alert check — no need to wait for the schedule.

---

## 7. Discord Alerts

When a tracking condition is met, the app sends a message to your Discord channel.

![Discord alert example](screenshots/Discord_alerts.png)

Each alert message includes:
- **Alert type** — e.g. 💰 Price Drop, 📦 Availability Alert, 📈 Price Increase
- **Product name** (clickable link to the product page)
- **Brand, Price, Size, Color**
- **Stock status and inventory count**
- **Product image thumbnail**

> **Cooldown:** The same alert won't be sent more than once per hour for the same product + state. This prevents your Discord from getting spammed if you have high-priority tracking on a product that keeps fluctuating.

---

## 8. Tips & Tricks

- **Tracking a hyped drop?** Set priority to 🔴 Urgent and schedule to Every Hour so you get alerted within minutes of a restock.
- **Only care about your size?** When setting up tracking, you can filter by specific sizes so you only get alerts that are relevant to you.
- **Multiple Discord channels?** You can set a different webhook per tracked product — useful if you want alerts for different products going to different channels.
- **Low Stock filter** catches products with fewer than 50 units in inventory — great for limited-stock items before they sell out entirely.
- **Sale + In Stock combo:** Use the 🔥 On Sale toggle alongside the In Stock filter on the Products page to find deals that are still available.
- **Dark mode:** Click the ☀️/🌙 icon in the top-right corner of any page to switch between light and dark mode.
