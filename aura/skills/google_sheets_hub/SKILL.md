---
name: google-sheets-cloud-hub
description: Universal Google Sheets Cloud & Daily P&L Engine. Use when Mukil asks about Google Sheets, creating custom spreadsheets, daily budget allocation, bleaching P&L, pulling edits from phone, or managing cloud ledgers.
---

# Google Sheets Cloud Hub & Financial P&L Engine

## 📌 Mission
Provides autonomous, permanent, zero-touch Google Sheets synchronization directly linked to Mukil's Google Drive Master Vault (`1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ`).

## ☁️ Active Cloud Master Sheets
1. **SGC Bleaching Unit - Daily P&L Master Ledger**:
   - ID: `1w3NVcCQv-pVV6MOz4sNcjD3VmSHGndyG4u4PKnG5FfQ`
   - URL: https://docs.google.com/spreadsheets/d/1w3NVcCQv-pVV6MOz4sNcjD3VmSHGndyG4u4PKnG5FfQ/edit
   - Tracks: Daily KGs bleached, production revenue, chemical expenses (H2O2, Caustic, Softener), EB power costs, wages, and net daily margin.
2. **SGC Daily Budget & Payment Tracker**:
   - ID: `1M1hbb0kzUgKycG6FG46i2agAx8ilIvrPYbm42aDD7vM`
   - URL: https://docs.google.com/spreadsheets/d/1M1hbb0kzUgKycG6FG46i2agAx8ilIvrPYbm42aDD7vM/edit
   - Tracks: Client cash inflows, daily budget allocation, and vendor payments.

## 🛠️ Execution Directives
- **Cloud-First Law**: NEVER provide a local Windows file path (`C:/...`) for spreadsheets. ALWAYS upload to Google Drive and provide the clickable live link.
- **Two-Way Mobile Sync**: When Mukil edits numbers directly on his phone in Google Sheets, call `check_and_update_bleaching_sheet()` to pull live edits, recalculate all P&L metrics, and re-sync to Drive.
- **Telegram Logging**:
  * Production: `record_bleaching_production(customer, material, kgs, rate_per_kg)`
  * Expenses: `record_bleaching_expense(category, item, vendor, amount)`
  * Summary: `get_bleaching_daily_summary()`
