# CloudVerse Telegram Bot Button Map (Admin Perspective)

This document provides an exact, code-accurate map of all Telegram bot buttons and menus as seen by an **admin user**.

---

## Main Menu (Admin)
- 📁 File Manager | 🔍 Search
- 🕶️Account Profile | 📊 Storage Details
- 🗑️ Recycle Bin | ⚙️ Settings
- 💬 Message Developer | 📃 Terms & Conditions
- 🔑 Access Control *(admin only)*
- 👑 Admin Control *(admin only)*

---

## File Manager
- Folder Options ⚙️
- 📂 [Folder Name] (one per folder)
- 📄 [File Name] (one per file)
- ✳️ Back (if inside a folder)
- Pagination: ◀️ Prev | [Page/Total] | Next ▶️ (if multiple pages)
- ✳️ Back (always at bottom)

### File Toolkit (after selecting a file)
- ✏️ Rename | ❎ Delete
- 🔗 Copy Link | 💾 Size
- ✳️ Back

### Folder Toolkit (after selecting Folder Options ⚙️)
- ✏️ Rename | ❎ Delete
- 📋 Copy Link | 🔗 Link Sharing: ON 🟢/OFF 🔴
- ✳️ Back

---

## Search
- 📂 [Folder Name] / 📄 [File Name] (search results)
- Next ▶️ | ◀️ Prev (pagination)
- ✳️ Back

---

## Recycle Bin
- 📂/[File Name] (trashed items)
- Pagination: ◀️ Prev | [Page/Total] | Next ▶️
- 🗑️ Empty Bin
- ✳️ Back

### Bin Item Toolkit (after selecting an item)
- ✅ Restore
- ❎ Permanent Delete
- ✳️ Back

### Empty Bin Confirmation
- Yes, empty | No, cancel

---

## Settings
- ❇️ Login
- ❎ Logout
- 👤 Switch Account
- 📂 Default Upload Location
- ⚡️ Parallel Uploads
- ✳️ Back

### Logout Options
- 🔓 Logout Account
- 🔐 Logout All
- ✳️ Back

---

## Access Control (Admin Only)
- 👑 Manage Admins
- 👀 White List
- 🚫 Black List
- 📝 Manage Requests
- ✳️ Back

### Admins/Whitelist/Blacklist/Requests Lists
- [User Label] (one per user)
- For Admins: 🤞 Demote | ❌ Remove (unless Super Admin)
- For Whitelist: ⏳ Set Limit/🗑️ Remove Limit | ♛ Promote | ❌ Remove
- For Blacklist: 🤝 Unrestrict | ✏️ Edit | ❌ Remove
- For Requests: ✅ Approve | ❌ Reject
- Pagination: ◀️ Prev | [Page/Total] | Next ▶️
- ✳️ Back
- ♻️ Refresh (for requests)

---

## Admin Control (Admin Only)
- 👑 Admin
- 👥 Users
- 📊 Analytics
- 🖥 Performance
- 📝 Edit Terms & Condition
- ✳️ Back

---

## Analytics Report Generator (Admin Only)
- 📋 Professional Report (10-15s)
- 📈 Dashboard Report (8-12s)
- 📜 Minimalist Report (5-8s)
- 🗃️ Individual reports
- ❌ Cancel

### Individual User List
- [User Label] (one per user)
- Pagination: ◀️ Prev | [Page/Total] | Next ▶️
- ✳️ Back

---

## Message Developer
- [Text input] (send message)
- ✳️ Back

---

## Terms & Conditions
- [Text]
- ✳️ Back

---

## Storage Details
- [Text]
- ✳️ Back

---

## Notes
- All menus may include pagination (◀️ Prev / Next ▶️) if there are multiple pages.
- Admins see additional controls not visible to regular users.
- Some buttons/toolkits are context-dependent (e.g., file/folder actions, bin item actions).
- Button order and grouping matches the real bot UI as coded. 