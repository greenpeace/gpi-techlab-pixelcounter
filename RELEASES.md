# Release Notes - Pixel Counter App

## [v1.1.0] - 2025-12-17

### 🚀 New Features
- **NRO Management System**: A dedicated administrative interface to manage National and Regional Offices (NROs).
  - Full CRUD capabilities (Create, Read, Update, Delete).
  - Interactive **Active/Inactive** status management using Switchery toggle sliders.
  - Advanced table features including instant search and pagination via **DataTables**.
- **Collaborative Multi-User Access**: Counters can now be shared across multiple users.
  - New **"Assigned Users"** multi-select tool in counter forms.
  - Enhanced visibility logic: users see counters they own, counters in their NRO, global counters, and counters specifically assigned to them.
- **Dynamic NRO Integration**: 
  - Counter creation and editing now use a curated dropdown list of active NROs, replacing manual text entry for better data consistency.

### 🛠️ Administrative Improvements
- **API Key Visibility**: Administrators can now monitor all API keys in the system, with clear visibility into which specific user owns each key.
- **Enhanced Data Management**: NRO selection is now integrated into User Profiles for automatic local counter visibility.

### 🎨 UI/UX Enhancements
- **Premium Interface Components**: Integrated **Switchery** for iOS-style toggles and **DataTables** for high-performance data handling.
- **Card-Based Layouts**: Standardized management pages to use the modern card-based layout for better visual consistency across the application.

### 🐛 Bug Fixes
- Resolved `NameError` related to missing `nro_ref` in pixelcounter backend.
- Fixed duplicate `created_at` field causing syntax errors in user profile management.
- Standardized template block naming (`script` vs `scripts`) to ensure reliable JavaScript execution.
- Fixed double-initialization of toggle sliders in NRO and API key lists.
- Corrected `.gitignore` conflicts to ensure all critical module files are properly managed.
