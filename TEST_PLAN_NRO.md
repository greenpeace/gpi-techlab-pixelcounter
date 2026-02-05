# Test Plan: NRO Management & Collaborative Access

This plan outlines the testing scenarios required to verify the NRO management system, multi-user assignment features, and the updated visibility logic across different user roles.

---

## 👥 Test Personas Needed
To perform these tests, you should ideally have access to:
1. **Admin User**: Role = `Administrator`
2. **User A**: Role = `user`, NRO = `GP Belgium`
3. **User B**: Role = `user`, NRO = `GP Canada`
4. **User C**: Role = `user`, NRO = `GP Belgium` (same NRO as User A)

---

## 🧪 Test Suite 1: NRO Management (Admin Only)
**Goal**: Verify the administration of offices.

| Step | Action | Expected Result |
| :--- | :--- | :--- |
| 1.1 | Login as **Admin**, go to **Admin > NRO Management**. | Page loads with DataTables search/pagination. |
| 1.2 | Search for an NRO using the search box. | Table filters in real-time. |
| 1.3 | Click the **Active slider** to deactivate an NRO (e.g., "GP Test"). | Switch turns gray. AJAX console log shows success. |
| 1.4 | Go to **Operations > Add Counter**. Check NRO dropdown. | Deactivated NRO ("GP Test") should **not** appear in the list. |
| 1.5 | Re-activate NRO in NRO Management. | Switch turns green. |
| 1.6 | Change entries per page to "All". | Table expands to show all NROs. |

---

## 🧪 Test Suite 2: Visibility Logic (Matrix Testing)
**Goal**: Verify that users see exactly what they are supposed to see based on the new logic.

### Scenario A: Ownership
*   **Action**: **User A** creates a counter named `belgium-private` with type `local` and NRO `GP Belgium`.
*   **Check**: **User A** sees it. **User B** (different NRO) should **not** see it.

### Scenario B: NRO Affiliation (Local Access)
*   **Action**: **Admin** creates a counter named `belgium-hq-local` with type `local` and NRO `GP Belgium`.
*   **Check**: **User A** and **User C** (both in Belgium) **both see it**. **User B** (Canada) does **not** see it.

### Scenario C: Global Counters
*   **Action**: Any user/Admin creates a counter named `global-fundraiser` with type `global`.
*   **Check**: **User A**, **User B**, and **User C** should all see it in their lists.

### Scenario D: Manual Assignment (The New Feature)
*   **Action**: **Admin** edits the `belgium-private` counter (owned by User A). In the **Assigned Users** list, selects **User B**.
*   **Check**: **User B** (who is in Canada) should now see `belgium-private` in their list, even though it's a local Belgium counter.

---

## 🧪 Test Suite 3: Data Integrity (Dropdowns & Forms)
**Goal**: Verify that manual text entry is effectively replaced.

| Step | Action | Expected Result |
| :--- | :--- | :--- |
| 3.1 | **Admin** edits **User B**'s profile. | The NRO selection is a dropdown of active NROs. |
| 3.2 | **User A** adds a new counter. | User doesn't type NRO; they select from the dropdown. |
| 3.3 | **Admin** edits an existing counter. | The NRO dropdown is pre-selected with the current office. |
| 3.4 | Multi-select users in the edit form (Ctrl/Cmd click). | Multiple items should be highlighted. Save and verify they persist on re-edit. |

---

## 🧪 Test Suite 4: UI/UX & Reliability
**Goal**: Verify components behave as expected.

- [ ] **DataTables Pagination**: Verify that when you navigate to Page 2 of the NRO list, the toggle switches still work.
- [ ] **CSRF Protection**: Perform a toggle or delete; verify it doesn't trigger a 403 Forbidden error.
- [ ] **State Persistence**: Deactivate an NRO, refresh the page, verify it is still inactive.
- [ ] **Search Sensitivity**: Verify the search box in the NRO list is case-insensitive.

---

## 📝 Reporting Results
Please note any variations where the "Actual Result" does not match the "Expected Result".
